import copy
import logging

from rpdk.core.contract.interface import Action, HandlerErrorCode, OperationStatus
from rpdk.core.contract.resource_client import (
    prune_properties_from_model,
    prune_properties_if_not_exist_in_path,
)
from rpdk.core.contract.suite.contract_asserts_commons import failed_event
from rpdk.core.contract.suite.resource.contract_asserts import (
    response_contains_primary_identifier,
    response_contains_resource_model_equal_updated_model,
    response_contains_unchanged_primary_identifier,
    response_does_not_contain_write_only_properties,
)

LOG = logging.getLogger(__name__)


@response_contains_primary_identifier
@response_does_not_contain_write_only_properties
def test_create_success(resource_client, current_resource_model):
    _status, response, _error_code = resource_client.call_and_assert(
        Action.CREATE, OperationStatus.SUCCESS, current_resource_model
    )
    return response


@failed_event(
    error_code=HandlerErrorCode.AlreadyExists,
    msg="A create handler MUST NOT create multiple resources given\
         the same idempotency token",
)
def test_create_failure_if_repeat_writeable_id(resource_client, current_resource_model):
    LOG.debug(
        "at least one identifier is writeable; "
        "performing duplicate-CREATE-failed test"
    )
    # Should fail, because different clientRequestToken for the same
    # resource model means that the same resource is trying to be
    # created twice.
    _status, _response, error_code = resource_client.call_and_assert(
        Action.CREATE, OperationStatus.FAILED, current_resource_model
    )
    return error_code


@response_contains_primary_identifier
@response_does_not_contain_write_only_properties
def test_read_success(resource_client, current_resource_model):
    _status, response, _error_code = resource_client.call_and_assert(
        Action.READ, OperationStatus.SUCCESS, current_resource_model
    )
    test_input_equals_output(
        resource_client, current_resource_model, response["resourceModel"]
    )
    return response


@failed_event(
    error_code=HandlerErrorCode.NotFound,
    msg="A read handler MUST return FAILED with a NotFound error code\
         if the resource does not exist",
)
def test_read_failure_not_found(
    resource_client,
    current_resource_model,
):
    _status, _response, error_code = resource_client.call_and_assert(
        Action.READ, OperationStatus.FAILED, current_resource_model
    )
    return error_code


def get_resource_model_list(resource_client, current_resource_model):
    _status, response, _error_code = resource_client.call_and_assert(
        Action.LIST, OperationStatus.SUCCESS, current_resource_model
    )
    next_token = response.get("nextToken")
    resource_models = response["resourceModels"]
    while next_token is not None:
        _status, next_response, _error_code = resource_client.call_and_assert(
            Action.LIST,
            OperationStatus.SUCCESS,
            current_resource_model,
            nextToken=next_token,
        )
        resource_models.extend(next_response["resourceModels"])
        next_token = next_response.get("nextToken")
    return resource_models


def test_model_in_list(resource_client, current_resource_model):
    resource_models = get_resource_model_list(resource_client, current_resource_model)
    return any(
        resource_client.is_primary_identifier_equal(
            resource_client.primary_identifier_paths,
            resource_model,
            current_resource_model,
        )
        for resource_model in resource_models
    )


def error_test_model_in_list(resource_client, current_resource_model, message):
    resource_models = get_resource_model_list(resource_client, current_resource_model)
    assertion_error_message = message
    for resource_model in resource_models:
        resource_model_primary_identifier = resource_client.get_primary_identifier(
            resource_client.primary_identifier_paths, resource_model
        )
        current_model_primary_identifier = resource_client.get_primary_identifier(
            resource_client.primary_identifier_paths, current_resource_model
        )
        if resource_model_primary_identifier != current_model_primary_identifier:
            assertion_error_message = (
                "%s \n Resource Model primary identifier %s does not match with "
                "Current Resource Model primary identifier %s \n Resource Model : %s"
                " \n Currrent Model : %s "
                % (
                    message,
                    resource_model_primary_identifier[0],
                    current_model_primary_identifier[0],
                    resource_model,
                    current_resource_model,
                )
            )
            return assertion_error_message
    return assertion_error_message


@response_contains_primary_identifier
@response_contains_unchanged_primary_identifier
@response_contains_resource_model_equal_updated_model
@response_does_not_contain_write_only_properties
def test_update_success(resource_client, update_resource_model, current_resource_model):
    _status, response, _error_code = resource_client.call_and_assert(
        Action.UPDATE,
        OperationStatus.SUCCESS,
        update_resource_model,
        current_resource_model,
    )
    return response


@failed_event(
    error_code=HandlerErrorCode.NotFound,
    msg="An update handler MUST return FAILED with a NotFound error code\
         if the resource did not exist prior to the update request",
)
def test_update_failure_not_found(resource_client, current_resource_model):
    update_model = resource_client.generate_update_example(current_resource_model)
    _status, _response, error_code = resource_client.call_and_assert(
        Action.UPDATE, OperationStatus.FAILED, update_model, current_resource_model
    )
    return error_code


def test_delete_success(resource_client, current_resource_model):
    _status, response, _error_code = resource_client.call_and_assert(
        Action.DELETE, OperationStatus.SUCCESS, current_resource_model
    )
    return response


@failed_event(
    error_code=HandlerErrorCode.NotFound,
    msg="A delete hander MUST return FAILED with a NotFound error code\
         if the resource did not exist prior to the delete request",
)
def test_delete_failure_not_found(resource_client, current_resource_model):
    _status, _response, error_code = resource_client.call_and_assert(
        Action.DELETE, OperationStatus.FAILED, current_resource_model
    )
    return error_code


def test_input_equals_output(resource_client, input_model, output_model):
    pruned_input_model = prune_properties_from_model(
        copy.deepcopy(input_model),
        set(
            list(resource_client.read_only_paths)
            + list(resource_client.write_only_paths)
        ),
    )

    pruned_output_model = prune_properties_from_model(
        copy.deepcopy(output_model), resource_client.read_only_paths
    )

    pruned_output_model = prune_properties_if_not_exist_in_path(
        pruned_output_model, pruned_input_model, resource_client.create_only_paths
    )

    resource_client.compare(pruned_input_model, pruned_output_model)
