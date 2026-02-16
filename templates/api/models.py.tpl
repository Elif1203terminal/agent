"""Data models for ${app_name}."""


class ${model_name}:
    """Represents a ${resource_singular}."""

    def __init__(self, ${init_params}):
        ${init_body}

    def to_dict(self):
        return {
            ${to_dict_body}
        }

    def __repr__(self):
        return f"<${model_name}(${repr_fields})>"
