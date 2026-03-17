from fastapi import HTTPException, status


class PhotosAppError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(PhotosAppError):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} not found: {id}", code="NOT_FOUND")


class DuplicateError(PhotosAppError):
    def __init__(self, resource: str, field: str):
        super().__init__(f"{resource} already exists with this {field}", code="DUPLICATE")


class ForbiddenError(PhotosAppError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, code="FORBIDDEN")


def not_found(resource: str = "Resource"):
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def forbidden(detail: str = "Forbidden"):
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
