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
    def __init__(
        self,
        milvus_host="117.72.168.188",
        milvus_port=19530,
        ollama_host=None,
        ollama_port=None,
        *,
        session=None,
    ):
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        base_url = os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            host = ollama_host or "117.72.168.188"
            port = ollama_port or 11434
            base_url = f"http://{host}:{port}"
        self.ollama_url = f"{base_url}/api/embeddings"
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL",
            "nomic-embed-text",
        ).strip()
        self.embedding_timeout = int(os.getenv("EMBEDDING_TIMEOUT", "60"))
        self._session = session or requests.Session()
        if session is None:
            self._session.trust_env = False
        self.collection_name = "ai_test_cases"
        self.dim = 768
        self.client = None

    def _init_milvus(self):
        try:
            from pymilvus import MilvusClient, DataType

            self.client = MilvusClient(uri=f"http://{self.milvus_host}:{self.milvus_port}")

            if not self.client.has_collection(collection_name=self.collection_name):
                schema = MilvusClient.create_schema(
                    auto_id=True,
                    enable_dynamic_field=True
                )
                schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
                schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)
                schema.add_field(field_name="prd_content", datatype=DataType.VARCHAR, max_length=65535)
                schema.add_field(field_name="test_points", datatype=DataType.VARCHAR, max_length=65535)

                self.client.create_collection(
                    collection_name=self.collection_name,
                    schema=schema,
                    index_params=MilvusClient.prepare_index_params(
                        field_name="vector",
                        metric_type="COSINE",
                        index_type="IVF_FLAT",
                        index_name="vector_index",
                        params={"nlist": 128}
                    )
                )
                print(f"[RAG] 新建集合，使用COSINE相似度索引")
            else:
                print(f"[RAG] 集合已存在")

            self.client.load_collection(self.collection_name)
            print(f"[RAG] Milvus连接成功，集合已加载")
            return True
        except Exception as e:
            print(f"[RAG] Milvus连接失败: {str(e)}")
            raise ConnectionError(f"Milvus连接失败: {str(e)}")

    def _get_embedding(self, text: str) -> list:
        try:
            response = self._session.post(
                self.ollama_url,
                json={"model": self.embedding_model, "prompt": text},
                timeout=self.embedding_timeout,
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

    def search_similar_cases(
        self,
        current_prd: str,
        top_k: int = 2,
        similarity_threshold: float = 0.60,
        raise_on_error: bool = False,
    ) -> tuple:
        print(f"[RAG] 开始检索，查询文本长度: {len(current_prd)}")
        print(f"[RAG] 相似度阈值: {similarity_threshold}")
        
        if self.client is None:
            try:
                self._init_milvus()
            except ConnectionError as e:
                print(f"[RAG] Milvus连接失败: {e}")
                if raise_on_error:
                    raise
                return "", 0.0, 0

        try:
            stats = self.client.get_collection_stats(self.collection_name)
            row_count = stats.get("row_count", 0)
            print(f"[RAG] 向量库中共有 {row_count} 条数据")
            if row_count == 0:
                return "", 0.0, 0
        except Exception as e:
            print(f"[RAG] 获取统计信息失败: {e}")
            if raise_on_error:
                raise RuntimeError(f"获取Milvus统计信息失败: {e}") from e
            return "", 0.0, 0

        try:
            query_vector = self._get_embedding(current_prd)
            print(f"[RAG] 查询向量长度: {len(query_vector)}")
            if not query_vector:
                if raise_on_error:
                    raise ValueError("Embedding向量为空")
                return "", 0.0, 0

            results = self.client.search(
                collection_name=self.collection_name,
                data=[query_vector],
                anns_field="vector",
                search_params={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["prd_content", "test_points"],
            )

            result_count = len(results[0]) if results and results[0] else 0
            print(f"[RAG] 检索结果数量: {result_count}")
            
            if not results or not results[0]:
                print("[RAG] 未检索到任何结果")
                return "", 0.0, 0

            context = ""
            matched_count = 0
            max_score = 0.0

            for i, hit in enumerate(results[0]):
                entity = hit.get("entity")
                if isinstance(entity, dict):
                    prd = entity.get("prd_content", "")
                    test = entity.get("test_points", "")
                else:
                    prd = ""
                    test = ""
                
                distance = hit.get("distance", 0)
                similarity = distance  # pymilvus>=2.4 COSINE metric: distance 即余弦相似度
                print(f"[RAG] 命中 {i+1}: distance={distance}, similarity={similarity:.4f}, prd_len={len(prd)}, test_len={len(test)}")

                if prd and test and similarity >= similarity_threshold:
                    print(f"[RAG] 命中 {i+1} 符合阈值要求，加入上下文")
                    
                    if similarity > max_score:
                        max_score = similarity
                    matched_count += 1
                    
                    context += f"【历史测试点 {i+1} - 相似度: {similarity:.4f}】\n"
                    context += f"需求摘要: {prd[:100]}...\n" if len(prd) > 100 else f"需求摘要: {prd}\n"
                    context += f"测试点内容:\n{test[:500]}...\n\n" if len(test) > 500 else f"测试点内容:\n{test}\n\n"
                else:
                    if not prd or not test:
                        print(f"[RAG] 命中 {i+1} 内容为空，跳过")
                    else:
                        print(f"[RAG] 命中 {i+1} 相似度太低 ({similarity:.4f})，低于阈值 {similarity_threshold}，跳过")

            print(f"[RAG] 最终返回上下文长度: {len(context)}, 最高相似度: {max_score:.4f}, 命中数量: {matched_count}")
            return context.strip(), max_score, matched_count
        except Exception as e:
            print(f"[RAG] 检索失败: {e}")
            import traceback
            traceback.print_exc()
            if raise_on_error:
                raise RuntimeError(f"Milvus检索失败: {e}") from e
            return "", 0.0, 0

    def get_total_count(self) -> int:
        try:
            if self.client is None:
                self._init_milvus()
            stats = self.client.get_collection_stats(self.collection_name)
            return stats.get("row_count", 0)
        except Exception:
            return 0
