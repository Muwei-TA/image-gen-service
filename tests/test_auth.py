from app.auth import ANSI_RE, CODE_RE, URL_RE


def test_device_login_output_parsing():
    output = (
        "Open this link https://auth.openai.com/codex/device\n"
        "Enter this one-time code\n"
        "\x1b[94m80JD-TOE2M\x1b[0m"
    )
    cleaned = ANSI_RE.sub("", output)
    assert URL_RE.search(cleaned).group(0) == "https://auth.openai.com/codex/device"
    assert CODE_RE.search(cleaned).group(0) == "80JD-TOE2M"


def test_device_code_pattern_does_not_match_product_names():
    assert CODE_RE.search("ChatGPT Codex OpenAI") is None
