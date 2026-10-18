"""Small independent examples checking metric meaning and edge cases."""
import unittest
import pandas as pd
from analysis import segment_metrics, snapshot_comparison, ranked_review_list, filter_listings

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        rows = []
        for date in ['2026-03-16', '2026-06-15']:
            for n, prices in [('A', [100., 200., None]), ('B', [300., 400.])]:
                for i, price in enumerate(prices):
                    rows.append(dict(id=f'{n}{i}', snapshot_date=date, neighbourhood_cleansed=n,
                        room_type='Entire home/apt', bedrooms=0., price=price,
                        availability_90=30., number_of_reviews_ltm=2., review_scores_value=4.,
                        minimum_nights=2., property_type='Apartment', accommodates=2.))
        self.data = pd.DataFrame(rows)

    def test_peer_quartiles_missing_and_ranking(self):
        metrics = segment_metrics(self.data, min_priced=2)
        a = metrics.loc[metrics.neighbourhood_cleansed.eq('A')].iloc[0]
        self.assertEqual((a.listings, a.price_n, a.median_price), (3, 2, 150))
        self.assertEqual((a.q1_price, a.q3_price), (125, 175))
        self.assertEqual(a.peer_median_price, 250)  # median of listings, not segment medians
        self.assertAlmostEqual(a.premium_pct, -40)
        ranked = ranked_review_list(snapshot_comparison(metrics))
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked.iloc[0].neighbourhood_cleansed, 'A')
        self.assertAlmostEqual(ranked.iloc[0].review_score, 40)

    def test_threshold_empty_and_unknown_bedrooms(self):
        m = segment_metrics(self.data, min_priced=3)
        self.assertTrue(m.premium_pct.isna().all())
        self.assertTrue(ranked_review_list(snapshot_comparison(m)).empty)
        unknown = self.data.copy(); unknown['bedrooms'] = float('nan')
        self.assertTrue(segment_metrics(unknown).empty)
        self.assertEqual(len(filter_listings(self.data, bedrooms=0)), len(self.data))
        self.assertTrue(segment_metrics(self.data, property_type='Absent').empty)

    def test_refinements_and_sensitivity_apply_to_peers(self):
        extra = self.data.iloc[[0]].assign(id='extra', price=3000, property_type='House')
        data = pd.concat([self.data, extra])
        a = segment_metrics(data, min_priced=1, property_type='Apartment').iloc[0]
        self.assertEqual(a.peer_price_n, 4)
        a = segment_metrics(data, min_priced=1, exclude_high_prices=True).iloc[0]
        self.assertEqual(a.peer_price_n, 4)

    def test_reversal_and_missing_snapshot_not_ranked(self):
        m = segment_metrics(self.data, min_priced=2)
        m.loc[m.snapshot_date.eq('2026-06-15'), 'premium_pct'] *= -1
        self.assertTrue(ranked_review_list(snapshot_comparison(m)).empty)
        self.assertTrue(ranked_review_list(snapshot_comparison(m.iloc[:2])).empty)

if __name__ == '__main__':
    unittest.main()
