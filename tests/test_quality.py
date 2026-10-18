import unittest
from scrapers.quality import review_reason

class QualityReviewTests(unittest.TestCase):
    def test_administrative_election_goes_to_review(self):
        self.assertIsNotNone(review_reason(
            {"title":"ELECCIÓN JUNTA DE VECINOS VILLA EL BOSQUE"},
            {"source_type":"municipal","commune":"Arauco"}))
    def test_national_ticketing_cannot_claim_florida_biobio(self):
        self.assertIsNotNone(review_reason(
            {"title":"Circo en Mall Cenco Florida"},
            {"source_type":"ticketing","commune":None,"radar_only":False}))
    def test_location_specific_ticketing_allowed(self):
        self.assertIsNone(review_reason(
            {"title":"Concierto de cámara"},
            {"source_type":"ticketing","commune":"Concepción","radar_only":False}))
    def test_official_community_activity_allowed(self):
        self.assertIsNone(review_reason(
            {"title":"Festival de Teatro Comunitario"},
            {"source_type":"municipal","commune":"Tomé","radar_only":False}))
    def test_radar_sources_are_review_only(self):
        self.assertIsNotNone(review_reason(
            {"title":"Actividad nocturna"},
            {"source_type":"media","radar_only":True}))
if __name__=="__main__":
    unittest.main()
