from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Joint2D(_message.Message):
    __slots__ = ("x", "y")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ...) -> None: ...

class Joint3D(_message.Message):
    __slots__ = ("x", "y", "z")
    X_FIELD_NUMBER: _ClassVar[int]
    Y_FIELD_NUMBER: _ClassVar[int]
    Z_FIELD_NUMBER: _ClassVar[int]
    x: float
    y: float
    z: float
    def __init__(self, x: _Optional[float] = ..., y: _Optional[float] = ..., z: _Optional[float] = ...) -> None: ...

class PersonPose(_message.Message):
    __slots__ = ("person_id", "joints_2d", "joints_3d", "confidence")
    PERSON_ID_FIELD_NUMBER: _ClassVar[int]
    JOINTS_2D_FIELD_NUMBER: _ClassVar[int]
    JOINTS_3D_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    person_id: int
    joints_2d: _containers.RepeatedCompositeFieldContainer[Joint2D]
    joints_3d: _containers.RepeatedCompositeFieldContainer[Joint3D]
    confidence: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, person_id: _Optional[int] = ..., joints_2d: _Optional[_Iterable[_Union[Joint2D, _Mapping]]] = ..., joints_3d: _Optional[_Iterable[_Union[Joint3D, _Mapping]]] = ..., confidence: _Optional[_Iterable[float]] = ...) -> None: ...

class PoseFrame(_message.Message):
    __slots__ = ("timestamp_ms", "source_id", "people")
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    PEOPLE_FIELD_NUMBER: _ClassVar[int]
    timestamp_ms: int
    source_id: str
    people: _containers.RepeatedCompositeFieldContainer[PersonPose]
    def __init__(self, timestamp_ms: _Optional[int] = ..., source_id: _Optional[str] = ..., people: _Optional[_Iterable[_Union[PersonPose, _Mapping]]] = ...) -> None: ...

class Ack(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...
