import html
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DATABASE_ID = "2eb03280d84c80a09c44d34b28c1fc5b"
PUBLIC_SITE = "https://satin-jaw-c6c.notion.site"
START = "<!-- NOTION-POSTS:START -->"
END = "<!-- NOTION-POSTS:END -->"


def notion_api(path, body=None):
    request = Request(
        f"https://api.notion.com/v1/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {os.environ['NOTION_TOKEN']}",
            "Notion-Version": "2025-09-03",
            "Content-Type": "application/json",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = json.loads(error.read().decode())
        raise RuntimeError(
            f"Notion API 오류 {error.code}: {detail.get('message', '')}"
        ) from None


def escape(value):
    # 표나 링크에 영향을 주는 문자를 처리한다.
    value = " ".join(str(value).split())
    value = html.escape(value).replace("|", "&#124;")
    for character in ("\\", "[", "]", "*", "_", "`"):
        value = value.replace(character, "\\" + character)
    return value


def main():
    readme = Path("README.md")
    original = readme.read_text(encoding="utf-8")

    if original.count(START) != 1 or original.count(END) != 1:
        raise RuntimeError("README에 START와 END 주석이 각각 하나씩 필요함.")

    start_index = original.index(START) + len(START)
    end_index = original.index(END)
    if start_index > end_index:
        raise RuntimeError("README 주석 순서가 잘못됨.")

    database = notion_api(f"databases/{DATABASE_ID}")
    sources = database.get("data_sources", [])
    if len(sources) != 1:
        raise RuntimeError(
            "데이터 소스를 하나로 결정할 수 없음. 데이터베이스 ID를 확인바람."
        )

    result = notion_api(
        f"data_sources/{sources[0]['id']}/query",
        {
            "page_size": 5,
            "filter": {
                "property": "날짜",
                "date": {"is_not_empty": True},
            },
            "sorts": [
                {"property": "날짜", "direction": "descending"}
            ],
        },
    )

    rows = [
        "| 날짜 | 태그 | 제목 |",
        "| --- | --- | --- |",
    ]

    for page in result["results"]:
        properties = page["properties"]
        title_property = next(
            prop for prop in properties.values()
            if prop["type"] == "title"
        )
        title = "".join(
            part["plain_text"] for part in title_property["title"]
        ) or "제목 없음"

        date = properties["날짜"]["date"]["start"][:10]
        tag_property = properties["태그"]

        if tag_property["type"] == "multi_select":
            tags = ", ".join(
                tag["name"] for tag in tag_property["multi_select"]
            )
        elif tag_property["type"] == "select":
            tag = tag_property["select"]
            tags = tag["name"] if tag else ""
        else:
            raise RuntimeError("태그는 선택 또는 다중 선택 속성이어야 함.")

        url = page.get("public_url") or (
            f"{PUBLIC_SITE}/{page['id'].replace('-', '')}"
        )
        rows.append(
            f"| {escape(date)} | {escape(tags)} | "
            f"[{escape(title)}]({url}) |"
        )

    if not result["results"]:
        content = "날짜가 지정된 학습 기록이 없음."
    else:
        content = "\n".join(rows)

    updated = (
        original[:start_index]
        + "\n\n" + content + "\n\n"
        + original[end_index:]
    )
    if updated != original:
        readme.write_text(updated, encoding="utf-8")
        print("README 업데이트 완료")
    else:
        print("변경 사항 없음")


if __name__ == "__main__":
    main()
