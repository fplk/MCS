from goals import *
import pytest
import uuid


def test_instantiate_object():
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'attributes': ['foo', 'bar'],
        'scale': 1.0
    }
    object_location = {
        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    obj = instantiate_object(object_def, object_location)
    assert type(obj['id']) is str
    for prop in ('type', 'mass'):
        assert object_def[prop] == obj[prop]
    for attribute in object_def['attributes']:
        assert obj[attribute] is True
    assert obj['shows'][0]['position'] == object_location['position']
    assert obj['shows'][0]['rotation'] == object_location['rotation']


def test_instantiate_object_offset():
    offset = {
        'x': random.random(),
        'z': random.random()
    }
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'scale': 1.0,
        'attributes': [],
        'offset': offset
    }
    x = random.random()
    z = random.random()
    object_location = {
        'position': {
            'x': x,
            'y': 0.0,
            'z': z
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    obj = instantiate_object(object_def, object_location)
    position = obj['shows'][0]['position']
    assert position['x'] == x - offset['x']
    assert position['z'] == z - offset['z']


def test_instantiate_object_materials():
    material_category = ['plastic']
    materials_list = materials.PLASTIC_MATERIALS
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'scale': 1.0,
        'attributes': [],
        'materialCategory': material_category
    }
    object_location = {
        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    obj = instantiate_object(object_def, object_location)
    assert obj['materials'][0] in (mat[0] for mat in materials_list)


def test_instantiate_object_salient_materials():
    salient_materials = ["plastic", "hollow"]
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'scale': 1.0,
        'attributes': [],
        'salientMaterials': salient_materials
    }
    object_location = {
        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    obj = instantiate_object(object_def, object_location)
    assert obj['salientMaterials'] == salient_materials
    for sm in salient_materials:
        assert sm in obj['info']


def test_instantiate_object_size():
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'scale': 1.0,
        'attributes': [],
    }
    object_location = {
        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    size_mapping = {
        'pickupable': 'light',
        'moveable': 'heavy',
        'anythingelse': 'massive'
    }
    for attribute in size_mapping:
        size = size_mapping[attribute]
        object_def['attributes'] = [attribute]
        obj = instantiate_object(object_def, object_location)
        assert size in obj['info']


def test_instantiate_object_choose():
    object_type = str(uuid.uuid4())
    mass = random.random()
    salient_materials = ["plastic", "hollow"]
    object_def = {
        'type': str(uuid.uuid4()),
        'info': [str(uuid.uuid4()), str(uuid.uuid4())],
        'mass': random.random(),
        'scale': 1.0,
        'attributes': [],
        'choose': [{
            'type': object_type,
            'mass': mass,
            'salientMaterials': salient_materials
        }]
    }
    object_location = {
        'position': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        },
        'rotation': {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0
        }
    }
    obj = instantiate_object(object_def, object_location)
    assert obj['type'] == object_type
    assert obj['mass'] == mass
    assert obj['salientMaterials'] == salient_materials


def test_RetrievalGoal_get_goal():
    goal_obj = RetrievalGoal()
    obj = {
        'id': str(uuid.uuid4()),
        'info': [str(uuid.uuid4())],
    }
    object_list = [obj]
    goal = goal_obj.get_config(object_list)
    assert goal['info_list'] == obj['info']
    target = goal['metadata']['target']
    assert target['id'] == obj['id']
    assert target['info'] == obj['info']


def test_TransferralGoal_get_goal_argcount():
    goal_obj = TransferralGoal()
    with pytest.raises(ValueError):
        goal_obj.get_config(['one object'])


def test_TransferralGoal_get_goal_argvalid():
    goal_obj = TransferralGoal()
    with pytest.raises(ValueError):
        goal_obj.get_config([{'attributes': ['']}, {'attributes': ['']}])


def test__generate_transferral_goal():
    goal_obj = TransferralGoal()
    extra_info = str(uuid.uuid4())
    pickupable_id = str(uuid.uuid4())
    pickupable_info_item = str(uuid.uuid4())
    pickupable_obj = {
        'id': pickupable_id,
        'info': [pickupable_info_item, extra_info],
        'pickupable': True
    }
    other_id = str(uuid.uuid4())
    other_info_item = str(uuid.uuid4())
    other_obj = {
        'id': other_id,
        'info': [other_info_item, extra_info],
        'attributes': []
    }
    goal = goal_obj.get_config([pickupable_obj, other_obj])

    combined_info = goal['info_list']
    assert set(combined_info) == {pickupable_info_item, other_info_item, extra_info}

    target1 = goal['metadata']['target_1']
    assert target1['id'] == pickupable_id
    assert target1['info'] == [pickupable_info_item, extra_info]
    target2 = goal['metadata']['target_2']
    assert target2['id'] == other_id
    assert target2['info'] == [other_info_item, extra_info]

    relationship = goal['metadata']['relationship']
    relationship_type = relationship[1]
    assert relationship_type in [g.value for g in TransferralGoal.RelationshipType]
