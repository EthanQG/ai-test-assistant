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
            print("向量库为空，先插入测试数据...")
            
            test_prd1 = "用户登录功能：支持手机号/邮箱登录，密码错误3次锁定账户，支持短信验证码登录"
            test_test1 = "测试点：1. 手机号登录 2. 邮箱登录 3. 密码错误3次锁定 4. 短信验证码登录"
            
            test_prd2 = "支付功能：支持微信支付、支付宝支付、银行卡支付，单笔限额10000元"
            test_test2 = "测试点：1. 微信支付 2. 支付宝支付 3. 银行卡支付 4. 单笔限额验证"
            
            rag_manager.save_case(test_prd1, test_test1)
            rag_manager.save_case(test_prd2, test_test2)
            print("测试数据插入完成")
            
            stats = rag_manager.client.get_collection_stats("ai_test_cases")
            row_count = stats.get("row_count", 0)
            print(f"向量库中共有 {row_count} 条数据")
        
        print("\n=== 测试1：查询相似需求 ===")
        query_text = "用户登录"
        print(f"查询文本: {query_text}")
        
        context, max_score, matched_count = rag_manager.search_similar_cases(query_text, top_k=2)
        print(f"\n返回结果:")
        print(f"context长度: {len(context)}")
        print(f"max_score: {max_score:.4f}")
        print(f"matched_count: {matched_count}")
        
        if context:
            print(f"\n上下文内容:\n{context}")
        else:
            print("未检索到符合阈值的结果")
        
        print("\n=== 测试2：查询不相关需求 ===")
        query_text = "天气预报功能"
        print(f"查询文本: {query_text}")
        
        context, max_score, matched_count = rag_manager.search_similar_cases(query_text, top_k=2)
        print(f"\n返回结果:")
        print(f"context长度: {len(context)}")
        print(f"max_score: {max_score:.4f}")
        print(f"matched_count: {matched_count}")
        
        if context:
            print(f"\n上下文内容:\n{context}")
        else:
            print("未检索到符合阈值的结果（正确！）")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_search()