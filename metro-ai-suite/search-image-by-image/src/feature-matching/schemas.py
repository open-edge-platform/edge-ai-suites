from marshmallow import Schema, fields


class BoundingBoxSchema(Schema):
    x_max = fields.Float(required=True)
    x_min = fields.Float(required=True)
    y_max = fields.Float(required=True)
    y_min = fields.Float(required=True)


class DetectionSchema(Schema):
    bounding_box = fields.Nested(BoundingBoxSchema, required=True)
    confidence = fields.Float(required=True)
    label = fields.Str(required=True)
    label_id = fields.Int(required=True)


class ModelSchema(Schema):
    name = fields.Str(required=True)


class ClassificationSchema(Schema):
    confidence = fields.Float(required=True)
    label = fields.Str(required=True)
    label_id = fields.Int(required=True)
    model = fields.Nested(ModelSchema, required=True)


class ObjectSchema(Schema):
    classification = fields.Nested(ClassificationSchema, required=False)
    detection = fields.Nested(DetectionSchema, required=False)
    h = fields.Int(required=True)
    region_id = fields.Int(required=False)
    roi_type = fields.Str(required=False)
    w = fields.Int(required=True)
    x = fields.Int(required=True)
    y = fields.Int(required=True)


class ResolutionSchema(Schema):
    height = fields.Int(required=True)
    width = fields.Int(required=True)


class TensorMetadataSchema(Schema):
    dims = fields.List(
        fields.List(fields.Int()), required=True
    )  # Nested list of integers
    name = fields.List(fields.Str(), required=True)


class ObjectDetectionSchema(Schema):
    objects = fields.List(fields.Nested(ObjectSchema), required=True)
    resolution = fields.Nested(ResolutionSchema, required=True)
    tags = fields.Dict(keys=fields.Str(), values=fields.Raw(), required=True)
    timestamp = fields.Int(required=True)
    frame_id = fields.Int(required=True)
    time = fields.Int(required=True)
    img_format = fields.Str(required=True)  # Add img_format as a string field
    tensor_metadata = fields.Nested(
        TensorMetadataSchema, required=True
    )  # Add tensor_metadata as a nested schema
