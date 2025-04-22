from marshmallow import Schema, fields, ValidationError

# Define a schema for validation
class TensorSchema(Schema):
    data = fields.List(fields.Float(), required=False)
    layer_name = fields.Str(required=False)
    dims = fields.List(fields.Int(), required=False)
    model_name = fields.Str(required=False)
    name = fields.Str(required=False)
    precision = fields.Str(required=False)
    layout = fields.Str(required=False)
    label_id = fields.Int(required=False)
    confidence = fields.Float(required=False)
    

class MetadataSchema(Schema):
    time = fields.Int(required=True)
    objects = fields.List(fields.Dict(), required=False)
    caps = fields.Str(required=False)
    frame_id = fields.Int(required=False)
    width = fields.Int(required=False)
    height = fields.Int(required=False)
    encoding_level = fields.Int(required=False)
    pipeline = fields.Dict(required=False)
    encoding_type = fields.Str(required=False)
    img_format = fields.Str(required=False)
    gva_meta = fields.List(fields.Dict(), required=False)
    img_handle = fields.Str(required=False)
    channels = fields.Int(required=False)
    resolution = fields.Dict(required=False)
    tags = fields.Dict(required=False)
    timestamp = fields.Int(required=False)

class PayloadSchema(Schema):
    metadata = fields.Nested(MetadataSchema, required=True)
    blob = fields.Raw(required=False)