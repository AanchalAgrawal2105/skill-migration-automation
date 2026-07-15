from greeting import legacy_greet


def test_legacy_greet() -> None:
    assert legacy_greet("Refer") == "Hello, Refer!"

