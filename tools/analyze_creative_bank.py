"""
Creative Bank 분석 스크립트 (google-genai SDK 사용)
E:\Creative bank 폴더의 영상/이미지를 Gemini로 분석해 카피/비주얼 패턴 추출

결과:
  E:\Creative bank\@분석자료\bank_analysis.json
  E:\Creative bank\@분석자료\processed_files.json
"""

import os
import json
import time
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ── 설정 ─────────────────────────────────────────────────────
CREATIVE_BANK_PATH = Path("E:/Creative bank")
OUTPUT_DIR         = CREATIVE_BANK_PATH / "@분석자료"
OUTPUT_JSON        = OUTPUT_DIR / "bank_analysis.json"
PROGRESS_JSON      = OUTPUT_DIR / "processed_files.json"

GAME_FOLDER_MAP = {
    "PC포커":           "pc_poker",
    "한게임포커 클래식": "pc_poker",
    "우파루 오딧세이":   "uparu_odyssey",
    "한게임 로얄홀덤":  "royal_holdem",
    "한게임 섯다&맞고": "sutda_matgo",
    "한게임 신맞고":    "shin_matgo",
    "한게임 포커":      "hangame_poker",
    "한게임 홀덤":      "hangame_holdem",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".gif"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

MODEL = "gemini-2.5-flash-preview-04-17"
REQUEST_INTERVAL = 4.0  # 무료 티어: 분당 15 요청
# ─────────────────────────────────────────────────────────────


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Gemini API 키를 입력하세요:")
        key = input().strip()
    if not key:
        print("API 키 없음. 종료합니다.")
        sys.exit(1)
    return key


def load_progress():
    if PROGRESS_JSON.exists():
        try:
            return set(json.loads(PROGRESS_JSON.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_progress(processed):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(
        json.dumps(sorted(processed), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_bank():
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_bank(bank):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def parse_json_array(raw):
    try:
        m = re.search(r'\[[\s\S]*?\]', raw)
        if m:
            arr = json.loads(m.group())
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass
    return []


def get_mime(file_path):
    ext = file_path.suffix.lower()
    return {
        ".mp4": "video/mp4", ".mov": "video/quicktime",
        ".webm": "video/webm", ".avi": "video/x-msvideo",
        ".gif": "image/gif", ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp"
    }.get(ext, "application/octet-stream")


def analyze_file(client, file_path, is_video):
    if is_video:
        prompt = f"""이 광고 영상({file_path.name})을 분석해줘.

다음을 추출해서 JSON 배열로만 반환해. 다른 설명 없이 JSON만:
- 화면에 표시된 자막/텍스트 (정확히)
- 성우/나레이션 음성 대사 (정확히)
- 핵심 카피 문구
- 비주얼 연출 특징 1줄 요약 (예: "AI 실사 여성 + 포커칩 + 붉은 배경")

형식: ["카피1", "카피2", "비주얼 설명"]
중복 제거, 빈 항목 제외. 최대 10개."""
    else:
        prompt = """이 광고 이미지를 분석해줘.
다음을 JSON 배열로만 반환해 (다른 설명 없이):
- 화면에 표시된 텍스트/카피 (정확히)
- 비주얼 연출 특징 1줄 요약

형식: ["카피1", "카피2", "비주얼 설명"]
빈 항목 제외. 최대 8개."""

    mime = get_mime(file_path)

    # 파일 업로드
    print(f"    업로드 중...")
    with open(file_path, "rb") as f:
        uploaded = client.files.upload(
            file=f,
            config={"mime_type": mime, "display_name": file_path.name}
        )

    # 처리 완료 대기 (영상만)
    if is_video:
        print(f"    처리 대기 중...")
        timeout = 120
        start = time.time()
        while uploaded.state.name == "PROCESSING":
            if time.time() - start > timeout:
                raise Exception("처리 시간 초과")
            time.sleep(3)
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state.name == "FAILED":
            raise Exception("파일 처리 실패")

    # 분석
    print(f"    분석 중...")
    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded, prompt]
    )

    # 파일 삭제
    try:
        client.files.delete(name=uploaded.name)
    except Exception:
        pass

    return parse_json_array(response.text.strip())


def main():
    from google import genai

    print("=" * 55)
    print("  Creative Bank 분석 스크립트")
    print(f"  모델: {MODEL}")
    print("=" * 55)

    api_key = get_api_key()
    client = genai.Client(api_key=api_key)

    processed = load_progress()
    bank = load_bank()
    print(f"\n이미 처리된 파일: {len(processed)}개")

    # 처리할 파일 목록 수집
    tasks = []
    for folder_name, game_id in GAME_FOLDER_MAP.items():
        folder = CREATIVE_BANK_PATH / folder_name
        if not folder.exists():
            continue
        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                continue
            rel = str(f.relative_to(CREATIVE_BANK_PATH))
            if rel in processed:
                continue
            tasks.append((game_id, f, rel, ext in VIDEO_EXTENSIONS))

    total = len(tasks)
    print(f"처리할 파일: {total}개")

    if total == 0:
        print("새로 처리할 파일이 없습니다.")
        return

    estimated_cost = total * 0.0015
    print(f"예상 비용: ${estimated_cost:.2f} (약 {int(estimated_cost * 1400)}원)")
    print(f"예상 시간: 약 {int(total * REQUEST_INTERVAL / 60)}분\n")
    print("시작하려면 Enter, 취소는 Ctrl+C:")
    input()

    errors = 0
    for i, (game_id, file_path, rel_path, is_video) in enumerate(tasks, 1):
        print(f"[{i}/{total}] {file_path.name[:55]}")

        try:
            entries = analyze_file(client, file_path, is_video)

            if entries:
                if game_id not in bank:
                    bank[game_id] = []
                existing = set(bank[game_id])
                new_entries = [e for e in entries if e not in existing]
                bank[game_id].extend(new_entries)
                print(f"    OK: {len(new_entries)}개 추출 (누적: {len(bank[game_id])}개)")
            else:
                print(f"    - 추출 없음")

            errors = 0  # 성공하면 에러 카운터 리셋

        except KeyboardInterrupt:
            print("\n중단됨. 저장 중...")
            break
        except Exception as e:
            print(f"    ERROR: {e}")
            errors += 1
            if errors > 10:
                print("연속 오류 10회 초과. 중단합니다.")
                break

        processed.add(rel_path)

        if i % 10 == 0:
            save_bank(bank)
            save_progress(processed)
            print(f"    [중간저장 - {i}/{total}]")

        time.sleep(REQUEST_INTERVAL)

    save_bank(bank)
    save_progress(processed)

    print("\n" + "=" * 55)
    print(f"완료! 결과: {OUTPUT_JSON}")
    print("\n게임별 추출 카피 수:")
    for game_id, entries in bank.items():
        print(f"  {game_id}: {len(entries)}개")


if __name__ == "__main__":
    main()
