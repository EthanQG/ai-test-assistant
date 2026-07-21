import os
import time
import requests


class KnowledgeBaseManager:
    def __init__(self):
        self.default_kb_path = "./knowledge/bug_experience.txt"
        self.history_points_dir = "./knowledge/history_points"

    def load_bug_experience(self, file_path: str = None) -> str:
        target_path = file_path or self.default_kb_path

        if not os.path.exists(target_path):
            return ""

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            return content
        except Exception as e:
            return ""

    def load_knowledge(self, file_path: str) -> str:
        return self.load_bug_experience(file_path)

    def save_knowledge(self, content: str, file_path: str = None) -> bool:
        target_path = file_path or self.default_kb_path

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            return False

    def load_history_test_points(self) -> str:
        if not os.path.exists(self.history_points_dir):
            return ""

        history_content = ""
        try:
            for filename in os.listdir(self.history_points_dir):
                if filename.endswith(".md"):
                    filepath = os.path.join(self.history_points_dir, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            lines = f.readlines()[:20]
                            file_content = "".join(lines).strip()
                            if file_content:
                                history_content += f"【历史测试点 - {filename}】\n{file_content}\n\n"
                    except Exception:
                        continue

            return history_content.strip()
        except Exception:
            return ""

    def save_test_points(self, content: str, prd_title: str = "") -> str:
        if not os.path.exists(self.history_points_dir):
            os.makedirs(self.history_points_dir, exist_ok=True)

        if prd_title:
            safe_title = prd_title[:5].strip().replace("/", "_").replace("\\", "_").replace(":", "_")
            safe_title = "".join(c for c in safe_title if c not in ['<', '>', ':', '"', '/', '\\', '|', '?', '*'])
            if not safe_title:
                safe_title = "untitled"
        else:
            safe_title = "untitled"

        timestamp = int(time.time())
        filename = f"{safe_title}_{timestamp}.md"
        filepath = os.path.join(self.history_points_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return filepath
        except Exception as e:
            raise ValueError(f"保存失败: {str(e)}")


class MilvusRAGManager:
    def __init__(self, milvus_host="117.72.168.188", milvus_port=19530, ollama_host="117.72.168.188", ollama_port=11434):
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.ollama_url = f"http://{ollama_host}:{ollama_port}/api/embeddings"
        self.collection_name = "ai_test_cases"
        self.dim = 768
        self.client = None

    def _init_milvus(self):
        try:
            from pymilvus import MilvusClient

            self.client = MilvusClient(uri=f"http://{self.milvus_host}:{self.milvus_port}")

            if not self.client.has_collection(collection_name=self.collection_name):
                schema = MilvusClient.create_schema(
                    auto_id=True,
                    enable_dynamic_field=True
                )
                schema.add_field(field_name="id", datatype="INT64", is_primary=True)
                schema.add_field(field_name="vector", datatype="FLOAT_VECTOR", dim=self.dim)
                schema.add_field(field_name="prd_content", datatype="VARCHAR", max_length=65535)
                schema.add_field(field_name="test_points", datatype="VARCHAR", max_length=65535)

                self.client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=MilvusClient.prepare_index_params(
                        field_name="vector",
                        metric_type="L2",
                        index_type="IVF_FLAT",
                        index_name="vector_index",
                        params={"nlist": 128}
                    )
                )

            self.client.load_collection(self.collection_name)
            print(f"[RAG] Milvus连接成功，集合已加载")
            return True
        except Exception as e:
            print(f"[RAG] Milvus连接失败: {str(e)}")
            raise ConnectionError(f"Milvus连接失败: {str(e)}")

    def _get_embedding(self, text: str) -> list:
        try:
            response = requests.post(
                self.ollama_url,
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("embedding", [])
        except Exception as e:
            raise ValueError(f"Ollama Embedding请求失败: {str(e)}")

    def save_case(self, prd_content: str, test_points: str) -> bool:
        if self.client is None:
            self._init_milvus()

        try:
            vector = self._get_embedding(prd_content)
            if not vector:
                raise ValueError("Embedding向量为空")

            self.client.insert(
                collection_name=self.collection_name,
                data=[{
                    "vector": vector,
                    "prd_content": prd_content,
                    "test_points": test_points
                }]
            )

            self.client.flush(collection_name=self.collection_name)
            return True
        except Exception as e:
            raise ValueError(f"保存到Milvus失败: {str(e)}")

    def search_similar_cases(self, current_prd: str, top_k: int = 2) -> str:
        print(f"[RAG] 开始检索，查询文本长度: {len(current_prd)}")
        
        if self.client is None:
            try:
                self._init_milvus()
            except ConnectionError as e:
                print(f"[RAG] Milvus连接失败: {e}")
                return ""

        try:
            stats = self.client.get_collection_stats(self.collection_name)
            row_count = stats.get("row_count", 0)
            print(f"[RAG] 向量库中共有 {row_count} 条数据")
            if row_count == 0:
                return ""
        except Exception as e:
            print(f"[RAG] 获取统计信息失败: {e}")
            return ""

        try:
            query_vector = self._get_embedding(current_prd)
            print(f"[RAG] 查询向量长度: {len(query_vector)}")
            if not query_vector:
                return ""

            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                anns_field="vector",
                search_params={"metric_type": "L2", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["prd_content", "test_points"],
            )

            print(f"[RAG] 检索结果: {results}")
            
            if not results or not results[0]:
                print("[RAG] 未检索到任何结果")
                return ""

            context = ""
            for i, hit in enumerate(results[0]):
                print(f"[RAG] 命中 {i+1}: {hit}")
                
                entity = hit.get("entity")
                if isinstance(entity, dict):
                    prd = entity.get("prd_content", "")
                    test = entity.get("test_points", "")
                else:
                    prd = ""
                    test = ""
                
                distance = hit.get("distance", 0)
                print(f"[RAG] 命中 {i+1}: distance={distance}, prd_len={len(prd)}, test_len={len(test)}")

                if prd and test:
                    similarity = 1.0 / (1.0 + distance)
                    print(f"[RAG] 相似度: {similarity:.4f}")
                    
                    if similarity > 0.01:
                        context += f"【历史测试点 {i+1} - 相似度: {similarity:.4f}】\n"
                        context += f"需求摘要: {prd[:100]}...\n" if len(prd) > 100 else f"需求摘要: {prd}\n"
                        context += f"测试点内容:\n{test[:500]}...\n\n" if len(test) > 500 else f"测试点内容:\n{test}\n\n"
                    else:
                        print(f"[RAG] 命中 {i+1} 相似度太低 ({similarity:.4f})，跳过")
                else:
                    print(f"[RAG] 命中 {i+1} 内容为空，跳过")

            print(f"[RAG] 最终返回上下文长度: {len(context)}")
            return context.strip()
        except Exception as e:
            print(f"[RAG] 检索失败: {e}")
            import traceback
            traceback.print_exc()
            return ""

    def get_total_count(self) -> int:
        try:
            if self.client is None:
                self._init_milvus()
            stats = self.client.get_collection_stats(self.collection_name)
            return stats.get("row_count", 0)
        except Exception:
            return 0