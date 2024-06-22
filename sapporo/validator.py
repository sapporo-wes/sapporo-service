from functools import lru_cache
from typing import List, Optional, Tuple

from fastapi import UploadFile
from fastapi.exceptions import RequestValidationError

from sapporo.factory import create_service_info
from sapporo.schemas import RunRequestForm


def validate_run_request(
    wf_params: Optional[str],
    wf_type: str,
    wf_type_version: Optional[str],
    tags: Optional[str],
    wf_engine: str,
    wf_engine_version: Optional[str],
    wf_engine_parameters: Optional[str],
    wf_url: Optional[str],
    wf_attachment: List[UploadFile],
    wf_attachment_obj: Optional[str],
) -> RunRequestForm:
    """\
    Validate and convert the form-data request sent to POST /runs.

    The form data is validated and converted into an intermediate RunRequestForm schema,
    which is then used to create the final RunRequest schema for internal use.
    """
    # wf_params = json.loads(workflow_params) if workflow_params else {}
    # if workflow_type is None:

    raise NotImplementedError("Not implemented")
    # return RunRequestForm(
    #     workflow_params=


# @lru_cache(maxsize=None)
# def validate_wf_type_and_version(
#     wf_type: str,
#     wf_type_version: Optional[str] = None,
# ) -> Tuple[str, str]:
#     """\
#     Validate the wf_type and wf_type_version.
#     If wf_type_version is None, get the first item from service-info.
#     """
#     service_info = create_service_info()
#     wf_types = service_info.workflow_type_versions.keys()
#     if wf_type not in wf_types:
#         raise RequestValidationError(errors=[f"Invalid workflow_type: {wf_type}"])
#     if wf_type_version is None:
#         wf_type_version = service_info.workflow_type_versions[wf_type][0]

#     return wf_type, wf_type_version


# [{'input': None,
#   'loc': ('body', 'workflow_engine'),
#   'msg': 'Field required',
#   'type': 'missing'}]
