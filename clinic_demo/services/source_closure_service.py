"""Compatibility entry point; all source journeys use the shared dispatcher."""
def complete_source_journeys(run):
    return run._journey_action('sources')








