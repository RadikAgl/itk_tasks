from datetime import datetime


class CreatingTimeAttrMeta(type):
    def __new__(cls, name, bases, attrs):
        attrs["_created_at"] = datetime.now()
        return super().__new__(cls, name, bases, attrs)

    @property
    def created_at(cls):
        return cls._created_at
