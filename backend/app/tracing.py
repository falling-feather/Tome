"""OpenTelemetry tracing bootstrap (P1-22).

设计目标：
- 未安装 opentelemetry-* 包时不影响服务启动（lazy import + try/except）。
- `settings.OTEL_ENABLED=False` 时全部 no-op，包括 `traced_span`。
- 提供一个 `traced_span(name, **attrs)` 上下文管理器，业务代码统一调用它，
  这样即便未来切换 backend 也不需要改业务侧。
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from backend.app.config import settings

logger = logging.getLogger("inkless.tracing")

_initialized = False
_tracer = None  # opentelemetry.trace.Tracer 或 None


def init_tracing(app=None) -> bool:
    """初始化 OTel SDK 与自动 instrumentation。返回是否启用成功。"""
    global _initialized, _tracer
    if _initialized:
        return _tracer is not None
    _initialized = True

    if not settings.OTEL_ENABLED:
        logger.info("OTel: 已禁用 (OTEL_ENABLED=false)，跳过初始化")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as e:
        logger.warning(
            "OTel: 缺少 opentelemetry SDK 依赖 (%s)，运行 `pip install opentelemetry-api opentelemetry-sdk` 启用",
            e,
        )
        return False

    resource = Resource.create({
        "service.name": settings.OTEL_SERVICE_NAME,
        "service.version": settings.APP_VERSION,
    })
    sampler = TraceIdRatioBased(max(0.0, min(1.0, settings.OTEL_SAMPLE_RATIO)))
    provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.OTEL_CONSOLE_EXPORT:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            otlp = OTLPSpanExporter(
                endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT.rstrip('/')}/v1/traces"
            )
            provider.add_span_processor(BatchSpanProcessor(otlp))
            logger.info("OTel: OTLP exporter -> %s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        except ImportError:
            logger.warning(
                "OTel: 已设置 OTEL_EXPORTER_OTLP_ENDPOINT 但缺少 opentelemetry-exporter-otlp-proto-http"
            )

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("inkless")

    # 自动 instrument FastAPI / SQLAlchemy / httpx — 失败不致命
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except ImportError:
            logger.debug("OTel: opentelemetry-instrumentation-fastapi 未安装，跳过")
        except Exception as e:  # 二次注册等
            logger.debug("OTel: FastAPIInstrumentor 安装失败: %s", e)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        logger.debug("OTel: opentelemetry-instrumentation-httpx 未安装，跳过")
    except Exception as e:
        logger.debug("OTel: HTTPXClientInstrumentor 安装失败: %s", e)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from backend.app.database import engine
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    except ImportError:
        logger.debug("OTel: opentelemetry-instrumentation-sqlalchemy 未安装，跳过")
    except Exception as e:
        logger.debug("OTel: SQLAlchemyInstrumentor 安装失败: %s", e)

    logger.info("OTel: 初始化完成 service=%s sample=%.2f", settings.OTEL_SERVICE_NAME, settings.OTEL_SAMPLE_RATIO)
    return True


@contextmanager
def traced_span(name: str, **attributes: Any) -> Iterator[Any]:
    """业务统一入口；未启用时为 no-op，业务代码无需关心 OTel 是否启用。"""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as span:
        for k, v in attributes.items():
            try:
                span.set_attribute(k, v)
            except Exception:
                pass
        yield span
