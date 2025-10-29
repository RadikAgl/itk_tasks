# Метакласс


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class MyMetaSingleton(metaclass=SingletonMeta):
    pass


a = MyMetaSingleton()
b = MyMetaSingleton()

print(a is b)


# Через метод __new__
class SingletonByNew:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance


a = SingletonByNew()
b = SingletonByNew()

print(a is b)


# Через импорт
def get_singleton():
    from src.task_1_26_utils import s

    return s


def get_singleton2():
    from src.task_1_26_utils import s

    return s


a = get_singleton()
b = get_singleton2()

print(a is b)
