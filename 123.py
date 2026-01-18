headers_main = ["Skladišta"]
headers_sub = [""]

rows = []

if mode == "complete":
    for cpe in schema_list:
        headers_main.append(cpe["label"])
        headers_sub.append("Količina")
else:
    for cpe in schema_list:
        headers_main.extend([cpe["label"]] * 3)
        headers_sub.extend(["Bez adaptera", "Bez daljinskog", "Bez oba"])

headers_main.append("Ažurirano")

headers_sub.append("")