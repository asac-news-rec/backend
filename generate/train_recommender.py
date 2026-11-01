"""합성 노출 CSV로 클릭 예측 모델을 학습하고 사용자별 Top N을 저장합니다."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

ROOT = Path(__file__).resolve().parent
FEATURES = [
    'category', 'publisher', 'device', 'hour', 'article_age_hours',
    'user_clicks_7d', 'user_category_click_share_7d',
    'article_impressions_24h', 'article_clicks_24h', 'article_ctr_24h',
]
CATEGORICAL = ['category', 'publisher', 'device']


def new_model():
    return CatBoostClassifier(
        iterations=200, depth=4, learning_rate=0.04, loss_function='Logloss',
        random_seed=42, thread_count=2, verbose=False, allow_writing_files=False,
    )


def load_data(path):
    data = pd.read_csv(path, encoding='utf-8-sig')
    required = set(FEATURES + ['clicked', 'request_id', 'user_id', 'article_id',
                              'article_title', 'impression_id', 'published_at',
                              'impression_time', 'label_window_end'])
    if required - set(data):
        raise ValueError(f'누락 컬럼: {sorted(required - set(data))}')
    if data[list(required)].isna().any().any():
        raise ValueError('필수 컬럼에 빈 값이 있습니다.')
    if data['impression_id'].duplicated().any():
        raise ValueError('impression_id가 중복됩니다.')
    for column in ['published_at', 'impression_time', 'label_window_end']:
        data[column] = pd.to_datetime(data[column], utc=True)
    if not data['clicked'].isin([0, 1]).all() or data['clicked'].nunique() != 2:
        raise ValueError('clicked에는 0과 1 두 클래스가 필요합니다.')
    if (data['published_at'] > data['impression_time']).any():
        raise ValueError('발행 전 노출 데이터가 있습니다.')
    if (data['label_window_end'] < data['impression_time']).any():
        raise ValueError('관찰 종료 시각이 노출 시각보다 빠릅니다.')
    for column in CATEGORICAL:
        data[column] = data[column].astype(str)
    for column in set(FEATURES) - set(CATEGORICAL):
        data[column] = pd.to_numeric(data[column], errors='raise')
        if not np.isfinite(data[column]).all():
            raise ValueError(f'{column}: 유한한 숫자만 허용합니다.')
    # 같은 추천 요청을 시간 분할 경계에서 나누지 않습니다.
    if (data.groupby('request_id')['impression_time'].nunique() != 1).any():
        raise ValueError('한 request_id에는 하나의 노출 시각이 필요합니다.')
    return data.sort_values(['impression_time', 'impression_id']).reset_index(drop=True)


def evaluate(data):
    times = sorted(data['impression_time'].unique())
    if len(times) < 2:
        raise ValueError('시간 분할에는 두 개 이상의 노출 시각이 필요합니다.')
    cutoff = times[min(len(times) - 1, max(1, int(len(times) * 0.75)))]
    train = data[(data['impression_time'] < cutoff) & (data['label_window_end'] < cutoff)]
    test = data[data['impression_time'] >= cutoff].copy()
    if train['clicked'].nunique() != 2:
        raise ValueError('시간 분할 후 학습 데이터에 두 클래스가 필요합니다.')
    model = new_model()
    model.fit(train[FEATURES], train['clicked'], cat_features=CATEGORICAL)
    test['predicted_click_probability'] = model.predict_proba(test[FEATURES])[:, 1]
    y = test['clicked'].to_numpy()
    p = np.clip(test['predicted_click_probability'].to_numpy(), 1e-12, 1 - 1e-12)
    rate = float(train['clicked'].mean())
    def loss(probability):
        return float(-np.mean(y * np.log(probability) + (1 - y) * np.log(1 - probability)))
    positive, negative = p[y == 1], p[y == 0]
    auc = (float(np.mean((positive[:, None] > negative) +
                        0.5 * (positive[:, None] == negative)))
           if len(positive) and len(negative) else None)
    return test, {
        'evaluation_method': 'chronological holdout; label windows end before train cutoff',
        'test_start': pd.Timestamp(cutoff).isoformat(),
        'train_rows': len(train), 'test_rows': len(test),
        'train_clicks': int(train.clicked.sum()), 'test_clicks': int(test.clicked.sum()),
        'log_loss': loss(p), 'constant_train_ctr_log_loss': loss(rate), 'roc_auc': auc,
        'limitation': 'Synthetic demonstration; not evidence of real recommendation quality',
    }


def candidate_features(data, now):
    # 관측이 끝난 이력만 사용해 후보 기사마다 추천 시점의 feature를 계산합니다.
    past = data[(data['impression_time'] < now) & (data['label_window_end'] < now)]
    catalog = data.drop_duplicates('article_id').sort_values('article_id')
    catalog = catalog[catalog['published_at'] <= now]
    recent = past[past['impression_time'] >= now - pd.Timedelta(hours=24)]
    recent_user = past[past['impression_time'] >= now - pd.Timedelta(days=7)]
    rows = []
    for user in sorted(past['user_id'].unique()):
        clicks = recent_user[(recent_user['user_id'] == user) & (recent_user['clicked'] == 1)]
        clicked_ids = set(past[(past['user_id'] == user) & (past['clicked'] == 1)]['article_id'])
        device = past[past['user_id'] == user].iloc[-1]['device']
        for _, article in catalog.iterrows():
            if article['article_id'] in clicked_ids:
                continue
            exposures = recent[recent['article_id'] == article['article_id']]
            count, clicked = len(exposures), int(exposures['clicked'].sum())
            rows.append({
                'user_id': user, 'article_id': article['article_id'],
                'article_title': article['article_title'], 'category': article['category'],
                'publisher': article['publisher'], 'device': device,
                'hour': now.tz_convert('Asia/Seoul').hour,
                'article_age_hours': (now - article['published_at']).total_seconds() / 3600,
                'user_clicks_7d': len(clicks),
                'user_category_click_share_7d': float((clicks.category == article['category']).mean()) if len(clicks) else 0,
                'article_impressions_24h': count, 'article_clicks_24h': clicked,
                'article_ctr_24h': clicked / count if count else 0,
            })
    if not rows:
        raise ValueError('이미 클릭한 기사를 제외한 후 추천 후보가 없습니다.')
    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'recommendation_sample.csv')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'recommendation_results')
    parser.add_argument('--top-k', type=int, default=10)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error('--top-k는 1 이상이어야 합니다.')
    data = load_data(args.input)
    test, metrics = evaluate(data)
    # 홀드아웃 평가 완료 후 전체 관측 데이터로 최종 추천용 모델을 별도 재학습합니다.
    model = new_model()
    model.fit(data[FEATURES], data['clicked'], cat_features=CATEGORICAL)
    now = data['label_window_end'].max() + pd.Timedelta(seconds=1)
    candidates = candidate_features(data, now)
    candidates['predicted_click_probability'] = model.predict_proba(candidates[FEATURES])[:, 1]
    candidates = candidates.sort_values(
        ['user_id', 'predicted_click_probability', 'article_id'], ascending=[True, False, True])
    candidates['rank'] = candidates.groupby('user_id').cumcount() + 1
    top = candidates[candidates['rank'] <= args.top_k].copy()
    metrics.update(final_model_training_rows=len(data), recommendation_time=now.tz_convert('Asia/Seoul').isoformat(),
                   features=FEATURES, categorical_features=CATEGORICAL,
                   candidate_policy='all articles present in CSV, excluding previously clicked articles',
                   context_policy='last observed device per user; shared inference timestamp',
                   top_k=args.top_k)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(args.output_dir / 'catboost_click_model.cbm'))
    for name, frame in [('top10_by_user.csv', top), ('candidate_scores.csv', candidates),
                        ('holdout_predictions.csv', test)]:
        frame.to_csv(args.output_dir / name, index=False, encoding='utf-8-sig')
    (args.output_dir / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    for user, group in top.groupby('user_id'):
        print(f'\n{user} Top {len(group)}')
        for _, row in group.iterrows():
            print(f'{row["rank"]:2d}. {row["predicted_click_probability"]:.4f} {row["article_title"]}')
    print(f'\n출력: {args.output_dir.resolve()}')


if __name__ == '__main__':
    main()
