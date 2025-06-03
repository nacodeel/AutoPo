def get_system():
    with open("./system.aisi", "r", encoding="utf8") as f:
        text = f.read()
    return text