import os
import unittest

from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from examples.simulations.run_use_case_02_report_ready_dataset import run_report_ready_simulation
from semantic_log_generator.namespaces import EMOML, ONYX, ORO, SCHEMA


class TestROS2MockReportReadySimulation(unittest.TestCase):
    def setUp(self) -> None:
        # Keep integration tests hermetic even if the developer environment exports SEGB_* vars.
        self._segb_env_keys = (
            "SEGB_API_URL",
            "SEGB_API_TOKEN",
            "SEGB_SHARED_CONTEXT_TIMEOUT_SECONDS",
            "SEGB_SHARED_CONTEXT_VERIFY_TLS",
            "SEGB_SHARED_CONTEXT_RAISE_ON_ERROR",
        )
        self._segb_env_backup = {key: os.environ.get(key) for key in self._segb_env_keys}
        for key in self._segb_env_keys:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key in self._segb_env_keys:
            os.environ.pop(key, None)
        for key, value in self._segb_env_backup.items():
            if value is not None:
                os.environ[key] = value

    def test_report_ready_simulation_logs_exam_anxiety_and_recovery_with_animals(self) -> None:
        result = run_report_ready_simulation()
        graph = result.graph
        ari_namespace = result.base_result.ari_namespace

        exam_news_message = URIRef(f"{ari_namespace}message_ari_exam_news_msg_1")
        apology_message = URIRef(f"{ari_namespace}message_ari_apology_msg_1")
        animal_news_message = URIRef(f"{ari_namespace}message_ari_animal_news_msg_1")
        gratitude_message = URIRef(f"{ari_namespace}message_ari_heard_gratitude_1")

        self.assertIn((exam_news_message, RDF.type, ORO.ResponseMessage), graph)
        self.assertIn((apology_message, RDF.type, ORO.ResponseMessage), graph)
        self.assertIn((animal_news_message, RDF.type, ORO.ResponseMessage), graph)
        self.assertIn((gratitude_message, RDF.type, ORO.InitialMessage), graph)

        self.assertIn(
            (
                exam_news_message,
                SCHEMA.text,
                Literal(
                    "Here is one headline: many students are anxious because an important exam is coming soon.",
                    lang="en",
                ),
            ),
            graph,
        )
        self.assertIn(
            (
                apology_message,
                SCHEMA.text,
                Literal("I am sorry, Maria. That exam news was not a good choice right now.", lang="en"),
            ),
            graph,
        )
        self.assertIn(
            (
                gratitude_message,
                SCHEMA.text,
                Literal("Thank you, ARI! That animal news made me very happy.", lang="en"),
            ),
            graph,
        )

        fear_intensities = []
        happiness_intensities = []
        for emotion in graph.subjects(RDF.type, ONYX.Emotion):
            category = graph.value(emotion, ONYX.hasEmotionCategory)
            intensity = graph.value(emotion, ONYX.hasEmotionIntensity)
            if category == EMOML.big6_fear and intensity is not None:
                fear_intensities.append(float(intensity))
            if category == EMOML.big6_happiness and intensity is not None:
                happiness_intensities.append(float(intensity))

        self.assertTrue(any(value >= 0.9 for value in fear_intensities))
        self.assertTrue(any(value >= 0.98 for value in happiness_intensities))


if __name__ == "__main__":
    unittest.main()
