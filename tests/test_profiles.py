import unittest

from chaos_pass.profiles import load_profile, profile_names

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

    def test_every_profile_loads(self):
        for name in profile_names():
            self.assertTrue(load_profile(name), name)

if __name__ == "__main__":
    unittest.main()
