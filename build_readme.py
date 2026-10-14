import html
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

DATABASE_ID = "2eb03280d84c80a09c44d34b28c1fc5b"
PUBLIC_SITE = "https://satin-jaw-c6c.notion.site"
START = "<!-- NOTION-POSTS:START -->"
END = "<!-- NOTION-POSTS:END -->"

# 태그 배지에 순서대로 적용할 색상
BADGE_COLORS = ("6366F1", "2563EB", "0891B2", "7C3AED")


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
    return html.escape(str(value), quote=True)


def make_badge(tag_name, index):
    # Shields.io에서 _와 -가 특수하게 해석되는 것을 방지
    badge_text = tag_name.replace("_", "__").replace("-", "--")
    encoded_text = quote(badge_text, safe="")
    color = BADGE_COLORS[index % len(BADGE_COLORS)]

    badge_url = (
        f"https://img.shields.io/badge/{encoded_text}-{color}"
        "?style=flat-square"
    )

    return (
        f'<img alt="{escape(tag_name)}" '
        f'src="{escape(badge_url)}" '
        'height="16"></sup>'
    )


def main():
    readme = Path("README.md")
    original = readme.read_text(encoding="utf-8")

    if original.count(START) != 1 or original.count(END) != 1:
        raise RuntimeError(
            "README에 START와 END 주석이 각각 하나씩 필요함."
        )

    start_index = original.index(START) + len(START)
    end_index = original.index(END)

    if start_index > end_index:
        raise RuntimeError("README 주석 순서가 잘못됨.")

    database = notion_api(f"databases/{DATABASE_ID}")
    sources = database.get("data_sources", [])

    if len(sources) != 1:
        raise RuntimeError(
            "데이터 소스를 하나로 결정할 수 없음. "
            "데이터베이스 ID를 확인바람."
        )

    result = notion_api(
        f"data_sources/{sources[0]['id']}/query",
        {
            "page_size": 10,
            "filter": {
                "and": [
                    {
                        "property": "날짜",
                        "date": {"is_not_empty": True},
                    },
                    {
                        "property": "태그",
                        "multi_select": {
                            "does_not_contain": "운동기록"
                        },
                    },
                ],
            },
            "sorts": [
                {"property": "날짜", "direction": "descending"}
            ],
        },
    )

    entries = []

    for page in result["results"]:
        properties = page["properties"]

        title_property = next(
            prop
            for prop in properties.values()
            if prop["type"] == "title"
        )
        title = "".join(
            part["plain_text"]
            for part in title_property["title"]
        ) or "제목 없음"

        date = properties["날짜"]["date"]["start"][:10]
        tag_property = properties["태그"]

        if tag_property["type"] == "multi_select":
            tag_names = [
                tag["name"]
                for tag in tag_property["multi_select"]
            ]
        elif tag_property["type"] == "select":
            tag = tag_property["select"]
            tag_names = [tag["name"]] if tag else []
        else:
            raise RuntimeError(
                "태그는 선택 또는 다중 선택 속성이어야 함."
            )

        badges = " ".join(
            make_badge(tag_name, index)
            for index, tag_name in enumerate(tag_names)
        )

        url = page.get("public_url") or (
            f"{PUBLIC_SITE}/{page['id'].replace('-', '')}"
        )

        # 같은 칸 안에서 제목 → 태그 배지 → 날짜 순서
        parts = [
            f'<a href="{escape(url)}">{escape(title)}</a>'
        ]
        if badges:
            parts.append(badges)
        parts.append(f"<small>{escape(date)}</small>")

        entries.append("<p>" + " - ".join(parts) + "</p>")

    content = (
        "\n".join(entries)
        if entries
        else "<p>표시할 학습 기록이 없음.</p>"
    )

    # HTML 표 안에서 Markdown으로 해석되지 않도록 빈 줄 없이 삽입
    updated = (
        original[:start_index]
        + "\n"
        + content
        + "\n"
        + original[end_index:]
    )

    if updated != original:
        readme.write_text(updated, encoding="utf-8")
        print("README 업데이트 완료")
    else:
        print("변경 사항 없음")


if __name__ == "__main__":
    main()
