"""LangSmith 追踪的安全封装。

装了 langsmith 就用它的 @traceable；没装则退化为 no-op 装饰器，不影响运行。
是否真正上报由环境变量 LANGSMITH_TRACING / LANGSMITH_API_KEY 决定（见 .env.example）。
"""
try:
    from langsmith import traceable  # noqa: F401
except Exception:  # 未安装 langsmith
    def traceable(*args, **kwargs):
        # 兼容 @traceable 和 @traceable(name=...) 两种写法
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def _decorator(fn):
            return fn
        return _decorator
