import unittest

from chaos_pass.profiles import REQUIRED_PROFILE_FIELDS, load_profile_definition, profile_names

class ProfileTests(unittest.TestCase):
    def test_required_profiles_exist(self):
        required = {
            "expert-baseline", "power-user", "chaos-goblin",
            "boundary-hunter", "wrong-way-user", "ui-gremlin",
            "performance-murderer", "persistence-demon", "state-breaker",
            "charlie", "random-chaos", "wildcard", "soak-monster",
            "regression-archaeologist", "full-chaos-pass",
        }
        self.assertTrue(required.issubset(set(profile_names())))

    def test_every_profile_has_complete_playbook(self):
        for name in profile_names():
            profile = load_profile_definition(name)
            self.assertTrue(REQUIRED_PROFILE_FIELDS.issubset(profile), name)
            self.assertEqual(profile["id"], name)
            for key in (
                "attack_surface_priority", "opening_moves", "escalation_ladder",
                "signature_tactics", "combination_rules", "handoff_triggers",
                "stop_conditions", "required_evidence", "scenarios",
            ):
                self.assertTrue(profile[key], f"{name}:{key}")

    def test_random_and_wildcard_are_distinct(self):
        random_profile = load_profile_definition("random-chaos")
        wildcard = load_profile_definition("wildcard")
        self.assertIn("replay", random_profile["mindset"].lower())
        self.assertIn("pivot", wildcard["mindset"].lower())
        self.assertNotEqual(random_profile["signature_tactics"], wildcard["signature_tactics"])

    def test_charlie_is_not_random(self):
        charlie = load_profile_definition("charlie")
        self.assertIn("not act randomly", charlie["mindset"].lower())
        self.assertTrue(any(t["name"] == "Workaround ladder" for t in charlie["signature_tactics"]))

if __name__ == "__main__":
    unittest.main()