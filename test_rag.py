import sys
sys.path.insert(0, '.')

from utils.knowledge_base import MilvusRAGManager

def test_rag_search():
    rag_manager = MilvusRAGManager()
    
    try:
        rag_manager._init_milvus()
        
        stats = rag_manager.client.get_collection_stats("ai_test_cases")
        row_count = stats.get("row_count", 0)
        print(f"向量库中共有 {row_count} 条数据")
        
        if row_count == 0:
            print("向量库为空")
            return
        
        query_text = "用户登录功能"
        
        print(f"\n开始检索: {query_text}")
        
        query_vector = rag_manager._get_embedding(query_text)
        print(f"查询向量长度: {len(query_vector)}")
        
        results = rag_manager.client.search(
            collection_name="ai_test_cases",
            data=[query_vector],
            anns_field="vector",
            search_params={"metric_type": "L2", "params": {"nprobe": 10}},
            limit=2,
            output_fields=["prd_content", "test_points"],
        )
        
        print(f"\n检索结果: {results}")
        
        if results and results[0]:
            for i, hit in enumerate(results[0]):
                print(f"\n命中 {i+1}: {hit}")
                
                entity = hit.get("entity")
                if isinstance(entity, dict):
                    prd = entity.get("prd_content", "")
                    test = entity.get("test_points", "")
                else:
                    prd = ""
                    test = ""
                
                distance = hit.get("distance", 0)
                print(f"distance: {distance}")
                print(f"prd_content长度: {len(prd)}")
                print(f"test_points长度: {len(test)}")
                
                if prd:
                    print(f"prd_content前100字: {prd[:100]}")
        else:
            print("未检索到任何结果")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_search()