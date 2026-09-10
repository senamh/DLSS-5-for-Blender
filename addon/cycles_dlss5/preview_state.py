"""Keep a completed snapshot visible while appearance/scene updates are queued."""


def same_view(first, second):
    # View/projection, visible rectangle, frame and shading mode must match.
    # A dependency-graph notification is not a new camera, nor a reason to
    # throw away a completed image while its replacement is being prepared.
    return first is not None and first[:4] == second[:4] and first[9] == second[9]


def matrix_key(matrix):
    # Ignore subpixel numeric jitter rather than comparing raw float matrices.
    return tuple(round(value, 6) for row in matrix for value in row)
