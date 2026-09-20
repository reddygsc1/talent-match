from src.clients import OpenRouterClient


class StubOpenRouter(OpenRouterClient):
    def __init__(self, response):
        self.response = response

    def json_completion(self, system, user, schema=None):
        return self.response


def test_requirement_source_quote_is_verified_against_jd():
    response = {"requirements": [
        {"id": "python", "name": "Python", "jd_excerpt": "production Python",
         "importance": "required", "type": "noul", "instructions": "Is Python demonstrated?",
         "criteria": None, "target": True},
        {"id": "mentor", "name": "Mentoring", "jd_excerpt": "must manage ten people",
         "importance": "preferred", "type": "noul", "instructions": "Is mentoring demonstrated?",
         "criteria": None, "target": True},
    ]}
    requirements = StubOpenRouter(response).create_requirements("Required: production Python. Preferred: mentoring.")
    assert requirements[0].source_verified is True
    assert requirements[1].source_verified is False


def test_realistic_provider_string_shapes_are_accepted():
    response = {"requirements": [{
        "id": "years", "name": "Experience", "jd_excerpt": "4+ years",
        "importance": "required", "type": "score", "instructions": "Rate years",
        "criteria": "0: None, 1: One, 2: Two, 3: Three, 4: Four, 5: Five",
        "target": "4",
    }]}
    requirement = StubOpenRouter(response).create_requirements("Required: 4+ years")[0]
    assert requirement.criteria[4] == "Four"
    assert requirement.target == 4
