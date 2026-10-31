from aidub.application.invalidation import (
    ArtifactStage,
    DependencyNode,
    InvalidationGraph,
)


def test_translation_invalidation_is_localization_and_utterance_scoped() -> None:
    graph = InvalidationGraph()
    graph.add(
        DependencyNode(
            "translation:bn:u1",
            ArtifactStage.TRANSLATION,
            localization_id="bn",
            utterance_id="u1",
        )
    )
    graph.add(
        DependencyNode(
            "voice:bn:u1",
            ArtifactStage.VOICE,
            localization_id="bn",
            utterance_id="u1",
        ),
        depends_on=("translation:bn:u1",),
    )
    graph.add(
        DependencyNode(
            "mix:bn",
            ArtifactStage.MIX,
            localization_id="bn",
        ),
        depends_on=("voice:bn:u1",),
    )
    graph.add(
        DependencyNode(
            "translation:hi:u1",
            ArtifactStage.TRANSLATION,
            localization_id="hi",
            utterance_id="u1",
        )
    )
    assert graph.invalidate_translation(localization_id="bn", utterance_id="u1") == {
        "translation:bn:u1",
        "voice:bn:u1",
        "mix:bn",
    }
