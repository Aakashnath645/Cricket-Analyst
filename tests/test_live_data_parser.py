from app.services.live_data import CricbuzzLiveService


def test_extract_matches_payload_from_escaped_html() -> None:
    html = (
        "<html><body><script>prefix "
        '"matchesList":{"matches":[{"match":{"matchInfo":{"matchId":123,"seriesName":"Sample Series",'
        '"matchDesc":"Final","matchFormat":"T20","state":"In Progress","status":"Live","shortStatus":"Live",'
        '"team1":{"teamName":"A"},"team2":{"teamName":"B"},"venueInfo":{"ground":"Ground","city":"City"}},'
        '"matchScore":{"team1Score":{"inngs1":{"runs":164,"wickets":7,"overs":19.6}}}}}],'
        '"responseLastUpdated":123456} suffix</script></body></html>'
    )

    service = CricbuzzLiveService()
    payload = service._extract_matches_payload(html)
    assert "matches" in payload
    assert len(payload["matches"]) == 1
    info = payload["matches"][0]["match"]["matchInfo"]
    assert info["seriesName"] == "Sample Series"
    assert info["matchFormat"] == "T20"
