from utils.task_naming import derive_task_name, safe_report_filename


def test_task_name_prefers_markdown_heading_and_removes_generic_prefix():
    assert derive_task_name(
        "# 需求名称：电商订单履约与优惠结算\n\n正文"
    ) == "电商订单履约与优惠结算"


def test_task_name_falls_back_to_first_meaningful_line():
    assert derive_task_name("\n\n用户登录失败五次后锁定账号") == (
        "用户登录失败五次后锁定账号"
    )


def test_long_summary_is_compacted_at_first_business_clause():
    assert derive_task_name(
        "订单创建与履约规则，涵盖购物车结算、库存锁定、优惠券使用和支付结果处理"
    ) == "订单创建与履约规则"


def test_report_filename_replaces_windows_invalid_characters():
    assert safe_report_filename('订单/支付:"规则"') == (
        "订单_支付__规则-测试分析报告.md"
    )
