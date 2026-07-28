from image_gen_mcp.media import MediaStore


def test_media_store_expires_items():
    now = [100.0]
    store = MediaStore(clock=lambda: now[0], token_factory=lambda: "token")
    token, _ = store.put(
        b"image",
        "image/png",
        "generated.png",
        ttl_seconds=10,
        max_items=2,
        max_total_bytes=100,
    )
    assert store.get(token) is not None
    now[0] = 111.0
    assert store.get(token) is None


def test_media_store_evicts_oldest_item_when_bounded():
    tokens = iter(("first", "second"))
    store = MediaStore(token_factory=lambda: next(tokens))
    first, _ = store.put(
        b"one",
        "image/png",
        "one.png",
        ttl_seconds=60,
        max_items=1,
        max_total_bytes=100,
    )
    second, _ = store.put(
        b"two",
        "image/png",
        "two.png",
        ttl_seconds=60,
        max_items=1,
        max_total_bytes=100,
    )
    assert store.get(first) is None
    assert store.get(second) is not None
