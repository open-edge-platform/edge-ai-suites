from google.protobuf import empty_pb2 as _empty_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Vital(_message.Message):
    __slots__ = ("device_id", "metric", "value", "unit", "timestamp", "waveform", "waveform_frequency_hz", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    METRIC_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    UNIT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    WAVEFORM_FIELD_NUMBER: _ClassVar[int]
    WAVEFORM_FREQUENCY_HZ_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    device_id: str
    metric: str
    value: float
    unit: str
    timestamp: int
    waveform: _containers.RepeatedScalarFieldContainer[float]
    waveform_frequency_hz: int
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, device_id: _Optional[str] = ..., metric: _Optional[str] = ..., value: _Optional[float] = ..., unit: _Optional[str] = ..., timestamp: _Optional[int] = ..., waveform: _Optional[_Iterable[float]] = ..., waveform_frequency_hz: _Optional[int] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class VitalResponse(_message.Message):
    __slots__ = ("success", "message")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    success: bool
    message: str
    def __init__(self, success: bool = ..., message: _Optional[str] = ...) -> None: ...
