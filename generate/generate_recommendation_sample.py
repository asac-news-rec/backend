"""외부 API 없이 합성 노출 데이터를 생성합니다. 실제 사용자 행동이 아닙니다."""
import argparse
import csv
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def generate(seed=42, requests=200):
    rng = random.Random(seed)
    start = datetime(2026, 10, 20, 9, tzinfo=timezone(timedelta(hours=9)))
    categories = ['금융', 'IT', '스포츠', '문화']
    articles = [dict(article_id=f'demo-news-{i:03}',
                     article_title=f'[합성 예제] {categories[i % 4]} 소식 {i:03}',
                     category=categories[i % 4], publisher=f'가상언론사{i % 3 + 1}',
                     published_at=start - timedelta(hours=i % 24 + 1))
                for i in range(40)]
    history = []
    for request in range(requests):
        now = start + timedelta(hours=request)
        user = f'u{request % 10 + 1:03}'
        preference = categories[(request % 10) % 4]
        device = rng.choice(['mobile', 'desktop'])
        # 현재 요청의 결과는 넣기 전에 피처를 계산합니다.
        known = [r for r in history if r['_end'] < now]
        user_clicks = [r for r in known if r['user_id'] == user and r['clicked']
                       and r['_time'] >= now - timedelta(days=7)]
        shares = Counter(r['category'] for r in user_clicks)
        recent = [r for r in known if r['_time'] >= now - timedelta(hours=24)]
        batch = []
        for position, article in enumerate(rng.sample(articles, 5), 1):
            exposures = [r for r in recent if r['article_id'] == article['article_id']]
            clicks = sum(r['clicked'] for r in exposures)
            # 가상의 선호도로 클릭 라벨을 만드는 교육용 시뮬레이션입니다.
            probability = 0.65 if article['category'] == preference else 0.12
            row = dict(is_synthetic='true', impression_id=f'demo-imp-{request * 5 + position:05}',
                       request_id=f'demo-req-{request:04}', user_id=user, **article,
                       impression_time=now.isoformat(),
                       label_window_end=(now + timedelta(minutes=30)).isoformat(),
                       position=position, device=device, hour=now.hour,
                       article_age_hours=(now - article['published_at']).total_seconds() / 3600,
                       user_clicks_7d=len(user_clicks),
                       user_category_click_share_7d=shares[article['category']] / len(user_clicks) if user_clicks else 0,
                       article_impressions_24h=len(exposures), article_clicks_24h=clicks,
                       article_ctr_24h=clicks / len(exposures) if exposures else 0,
                       clicked=int(rng.random() < probability), _time=now,
                       _end=now + timedelta(minutes=30))
            row['published_at'] = article['published_at'].isoformat()
            batch.append(row)
        history.extend(batch)
    return [{k: v for k, v in row.items() if not k.startswith('_')} for row in history]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'sample_data' / 'impressions.csv')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--requests', type=int, default=200)
    args = parser.parse_args()
    if args.requests < 20:
        parser.error('--requests는 20 이상이어야 합니다.')
    rows = generate(args.seed, args.requests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f'합성 노출 {len(rows)}건 저장: {args.output.resolve()}')


if __name__ == '__main__':
    main()
