with open("test_output.txt", "rb") as f:
    text = f.read().decode("utf-16le", errors="ignore")
    with open("utf8_out.txt", "w", encoding="utf-8") as out:
        out.write(text)
