from io import BytesIO

import streamlit as st

from views.tab_test_points import (
    STATE_KEY,
    _create_agent_task,
    _initialize_session,
)


class UploadedRequirement(BytesIO):
    name = "requirement.md"


_initialize_session()
if st.button("创建文本任务"):
    _create_agent_task("用户可以提交订单", None)
if st.button("创建文件任务"):
    uploaded = UploadedRequirement(
        "# 订单需求\n\n库存不足时禁止创建订单。".encode("utf-8")
    )
    _create_agent_task("", uploaded)

state = st.session_state[STATE_KEY]
if state is not None:
    st.write(state.requirement)
