import argparse

import machine_common_sense as mcs


def parse_args():
    parser = argparse.ArgumentParser(description='Run MCS')
    parser.add_argument(
        'mcs_unity_build_file',
        help='Path to MCS unity build file')
    return parser.parse_args()


def run_scene(file_name, action_list):
    config_data, status = mcs.load_config_json_file(file_name)

    if status is not None:
        print(status)
        return

    config_file_path = file_name
    config_file_name = config_file_path[config_file_path.rfind('/') + 1:]

    if 'name' not in config_data.keys():
        config_data['name'] = config_file_name[0:config_file_name.find('.')]

    output = controller.start_scene(config_data)

    output = controller.step('Pass')

    for action in action_list:
        output = controller.step(action)  # noqa: F841

    controller.end_scene("", 1)


if __name__ == "__main__":
    args = parse_args()
    controller = mcs.create_controller(
        args.mcs_unity_build_file,
        debug=True,
        depth_masks=True,
        object_masks=True)

    run_scene('../scenes/eval_sample_1.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_2.json', [
        'RotateLook,horizon=60',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_3.json', [
        'RotateLook,rotation=90',
        'RotateLook,rotation=90',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_4.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,rotation=90',
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_5.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=45',
        'OpenObject,objectId=box_1,amount=1',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_6.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_7.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_8.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=ball_2'
    ])

    run_scene('../scenes/eval_sample_9.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=45',
        'OpenObject,objectId=box_1,amount=1',
        'PickupObject,objectId=ball_1'
    ])

    run_scene('../scenes/eval_sample_10.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=block_1'
    ])

    run_scene('../scenes/eval_sample_11.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=block_1'
    ])

    run_scene('../scenes/eval_sample_12.json', [
        'MoveAhead,amount=1',
        'MoveAhead,amount=1',
        'RotateLook,horizon=30',
        'PickupObject,objectId=bowl_1'
    ])