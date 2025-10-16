import random


def random_email():
    return f"test{random.randint(1, 1000000)}@test.com"


def random_base_path():
    return f"/tmp/syftbox{random.randint(1, 1000000)}"
