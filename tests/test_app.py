import unittest
from .context import app
from app import app, SERVICE_ROOT_PATH, FIND_TERMS_METHOD_NAME
from tempfile import TemporaryDirectory
from dsconcept.get_metrics import StubBestEstimator, HierarchicalClassifier
from sklearn.feature_extraction import DictVectorizer
import json


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.d = TemporaryDirectory()
        cat_clfs = [
            {"best_estimator_": StubBestEstimator(), "concept": "physics"},
            {"best_estimator_": StubBestEstimator(), "concept": "video games"},
        ]
        kwd_clfs = {
            ("physics", "gamma ray"): StubBestEstimator(),
            ("video games", "minecraft"): StubBestEstimator(),
            ("video games", "kerbal space program"): StubBestEstimator(),
            ("", "minecraft"): StubBestEstimator(),
            ("", "gamma ray"): StubBestEstimator(),
            ("", "penguins"): StubBestEstimator(),
        }
        v = DictVectorizer()
        d = [{"astronauts": 1, "astronomy": 1}, {"space": 1, "basalt": 1}]
        v.fit(d)
        app.config["HIER_CLF"] = HierarchicalClassifier(cat_clfs, kwd_clfs)
        app.config["HIER_CLF"].vectorizer = v
        app.config["CAT_RAW2LEMMA"] = {
            "PHYSICS": "physics",
            "VIDEO GAMES": "video games",
        }
        app.config["CAT_LEMMA2RAW"] = {
            v: k for k, v in app.config["CAT_RAW2LEMMA"].items()
        }
        app.config["KWD_RAW2LEMMA"] = {
            "MINECRAFT": "minecraft",
            "GAMMA RAY": "gamma ray",
            "KERBAL SPACE PROGRAM": "kerbal space program",
            "PENGUINS": "penguins",
        }
        app.config["KWD_LEMMA2RAW"] = {
            v: k for k, v in app.config["KWD_RAW2LEMMA"].items()
        }
        app.config["WEIGHTS"] = {
            "NOUN": 1,
            "NOUN_CHUNK": 1,
            "ENT": 1,
            "PROPN": 1,
            "ACRONYM": 1,
        }
        self.app = app.test_client()

    def test_home(self):
        response = self.app.get(f"{SERVICE_ROOT_PATH}/")
        self.assertEqual(response.status_code, 200)

    def test_find_terms(self):
        data = {
            "text": [
                "Astronauts go on space walks.",
                "Basalt rocks and minerals are on earth.",
            ],
            "probability_threshold": "0.5",
            "topic_threshold": "0.9",
            "request_id": "example_id10",
        }
        response = self.app.post(
            f"{SERVICE_ROOT_PATH}/{FIND_TERMS_METHOD_NAME}/",
            data=json.dumps(data),
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        r_data = json.loads(response.data)
        for rt in ["features", "sti_keywords", "topic_probabilities"]:
            self.assertEqual(len(r_data["payload"][rt]), 2)

    def test_find_terms_single(self):
        data = {
            "text": "Astronauts go on space walks.",
            "probability_threshold": "0.5",
            "topic_threshold": "0.9",
            "request_id": "example_id10",
        }
        response = self.app.post(
            f"{SERVICE_ROOT_PATH}/{FIND_TERMS_METHOD_NAME}/",
            data=json.dumps(data),
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        r_data = json.loads(response.data)
        for rt in ["features", "sti_keywords", "topic_probabilities"]:
            self.assertEqual(len(r_data["payload"][rt]), 1)


if __name__ == "__main__":
    unittest.main()
