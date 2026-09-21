"""Keep sustained qualification independent of variable manual setup time."""
def active_seconds(target_seconds, initial_active, resumed_elapsed):
    # 8-second fault/journey smokes keep their existing split-epoch workload.
    # Qualification measures 30/600 seconds with scripted controls after resume;
    # slow manual port inspection must not consume that sustained-input interval.
    return resumed_elapsed if target_seconds in (30, 600) else initial_active + resumed_elapsed
