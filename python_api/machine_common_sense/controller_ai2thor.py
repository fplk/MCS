import copy
import datetime
import glob
import io
import json
import os
import random
import sys
import yaml
import PIL
from typing import Dict, List

import ai2thor.controller
import ai2thor.server

# How far the player can reach.  I think this value needs to be bigger
# than the MAX_MOVE_DISTANCE or else the player may not be able to move
# into a position to reach some objects (it may be mathematically impossible).
# TODO Reduce this number once the player can crouch down to reach and
# pickup small objects on the floor.
MAX_REACH_DISTANCE = 1.0

# How far the player can move with a single step.
MAX_MOVE_DISTANCE = 0.5

# Performer camera 'y' position
PERFORMER_CAMERA_Y = 0.4625

from .action import Action
from .controller import Controller
from .goal_metadata import GoalMetadata
from .object_metadata import ObjectMetadata
from .pose import Pose
from .return_status import ReturnStatus
from .reward import Reward
from .scene_history import SceneHistory
from .step_metadata import StepMetadata
from .util import Util

# From https://github.com/NextCenturyCorporation/ai2thor/blob/master/ai2thor/server.py#L232-L240 # noqa: E501


def __image_depth_override(self, image_depth_data, **kwargs):
    # The MCS depth shader in Unity is completely different now, so override
    # the original AI2-THOR depth image code.
    # Just return what Unity sends us.
    image_depth = ai2thor.server.read_buffer_image(
        image_depth_data, self.screen_width, self.screen_height, **kwargs)
    return image_depth


ai2thor.server.Event._image_depth = __image_depth_override


class ControllerAI2THOR(Controller):
    """
    MCS Controller class implementation for the MCS wrapper of the AI2-THOR
    library.

    https://ai2thor.allenai.org/ithor/documentation/

    Parameters
    ----------
    debug : boolean, optional
        Whether to save MCS output debug files in this folder.
        (default False)
    enable_noise : boolean, optional
        Whether to add random noise to the numerical amounts in movement
        and object interaction action parameters.
        (default False)
    seed : int, optional
        A seed for the Python random number generator.
        (default None)
    """

    ACTION_LIST = [item.value for item in Action]

    # Please keep the aspect ratio as 3:2 because the IntPhys scenes are built
    # on this assumption.
    SCREEN_WIDTH_DEFAULT = 600
    SCREEN_WIDTH_MIN = 450

    # AI2-THOR creates a square grid across the scene that is
    # uses for "snap-to-grid" movement. (This value may not
    # really matter because we set continuous to True in
    # the step input.)
    GRID_SIZE = 0.1

    # The amount of force to offset force values, that seems
    # appropriate for a baby
    # TODO Check with psych team about this about what we
    # should use for a baby, defaulting to 50 now
    MAX_BABY_FORCE = 50.0

    DEFAULT_HORIZON = 0
    DEFAULT_ROTATION = 0
    DEFAULT_FORCE = 0.5
    DEFAULT_AMOUNT = 0.5
    DEFAULT_DIRECTION = 0
    DEFAULT_OBJECT_MOVE_AMOUNT = 1

    MAX_ROTATION = 360
    MIN_ROTATION = -360
    MAX_HORIZON = 180
    MIN_HORIZON = -180

    MAX_FORCE = 1
    MIN_FORCE = 0
    MAX_AMOUNT = 1
    MIN_AMOUNT = 0

    ROTATION_KEY = 'rotation'
    HORIZON_KEY = 'horizon'
    FORCE_KEY = 'force'
    AMOUNT_KEY = 'amount'
    OBJECT_DIRECTION_X_KEY = 'objectDirectionX'
    OBJECT_DIRECTION_Y_KEY = 'objectDirectionY'
    OBJECT_DIRECTION_Z_KEY = 'objectDirectionZ'
    RECEPTACLE_DIRECTION_X = 'receptacleObjectDirectionX'
    RECEPTACLE_DIRECTION_Y = 'receptacleObjectDirectionY'
    RECEPTACLE_DIRECTION_Z = 'receptacleObjectDirectionZ'

    # Hard coding actions that effect MoveMagnitude so the appropriate
    # value is set based off of the action
    # TODO: Move this to an enum or some place, so that you can determine
    # special move interactions that way
    FORCE_ACTIONS = ["ThrowObject", "PushObject", "PullObject"]
    OBJECT_MOVE_ACTIONS = ["CloseObject", "OpenObject"]
    MOVE_ACTIONS = ["MoveAhead", "MoveLeft", "MoveRight", "MoveBack"]

    HISTORY_DIRECTORY = "SCENE_HISTORY"

    CONFIG_FILE = os.getenv('MCS_CONFIG_FILE_PATH', './mcs_config.yaml')

    AWS_CREDENTIALS_FOLDER = os.path.expanduser('~') + '/.aws/'
    AWS_CREDENTIALS_FILE = os.path.expanduser('~') + '/.aws/credentials'
    AWS_ACCESS_KEY_ID = 'aws_access_key_id'
    AWS_SECRET_ACCESS_KEY = 'aws_secret_access_key'

    CONFIG_AWS_ACCESS_KEY_ID = 'aws_access_key_id'
    CONFIG_AWS_SECRET_ACCESS_KEY = 'aws_secret_access_key'
    CONFIG_METADATA_MODE = 'metadata'
    # Normal metadata plus metadata for all hidden objects
    CONFIG_METADATA_MODE_FULL = 'full'
    # No navigation metadata like 3D coordinates
    CONFIG_METADATA_MODE_NO_NAVIGATION = 'no_navigation'
    # No vision (image feature) metadata, except for the images
    CONFIG_METADATA_MODE_NO_VISION = 'no_vision'
    # No metadata, except for the images and haptic/audio feedback
    CONFIG_METADATA_MODE_NONE = 'none'
    CONFIG_SAVE_IMAGES_TO_S3_BUCKET = 'save_images_to_s3_bucket'
    CONFIG_SAVE_IMAGES_TO_S3_FOLDER = 'save_images_to_s3_folder'
    CONFIG_TEAM = 'team'

    HEATMAP_IMAGE_PREFIX = 'heatmap'

    def __init__(self, unity_app_file_path, debug=False,
                 enable_noise=False, seed=None, size=None,
                 depth_masks=False, object_masks=False):
        super().__init__()

        self._update_screen_size(size)

        self._controller = ai2thor.controller.Controller(
            quality='Medium',
            fullscreen=False,
            # The headless flag does not work for me
            headless=False,
            local_executable_path=unity_app_file_path,
            width=self.__screen_width,
            height=self.__screen_height,
            # Set the name of our Scene in our Unity app
            scene='MCS',
            logs=True,
            # This constructor always initializes a scene, so add a scene
            # config to ensure it doesn't error
            sceneConfig={
                "objects": []
            }
        )

        self._on_init(debug, enable_noise, seed, depth_masks,
                      object_masks)

    def _update_screen_size(self, size=None):
        self.__screen_width = self.SCREEN_WIDTH_DEFAULT
        self.__screen_height = self.SCREEN_WIDTH_DEFAULT / 3 * 2
        if size and size >= self.SCREEN_WIDTH_MIN:
            self.__screen_width = size
            self.__screen_height = size / 3 * 2

    def _update_internal_config(self, enable_noise=None, seed=None,
                                depth_masks=None, object_masks=None):

        if enable_noise is not None:
            self.__enable_noise = enable_noise
        if seed is not None:
            self.__seed = seed
        if depth_masks is not None:
            self.__depth_masks = depth_masks
        if object_masks is not None:
            self.__object_masks = object_masks

    def _on_init(self, debug=False, enable_noise=False, seed=None,
                 depth_masks=False, object_masks=False):

        self.__debug_to_file = True if (
            debug is True or debug == 'file') else False
        self.__debug_to_terminal = True if (
            debug is True or debug == 'terminal') else False

        self.__enable_noise = enable_noise
        self.__depth_masks = depth_masks
        self.__object_masks = object_masks
        self.__seed = seed

        if self.__seed:
            random.seed(self.__seed)

        self._goal = GoalMetadata()
        self.__head_tilt = 0.0
        self.__history_list = []
        self.__output_folder = None  # Save output image files to debug
        self.__scene_configuration = None
        self.__scene_history_file = None
        self.__step_number = 0
        self.__s3_client = None

        if not os.path.exists(self.HISTORY_DIRECTORY):
            os.makedirs(self.HISTORY_DIRECTORY)

        self._config = self.read_config_file()

        if ((self.CONFIG_AWS_ACCESS_KEY_ID in self._config) and
                (self.CONFIG_AWS_SECRET_ACCESS_KEY in self._config)):
            if not os.path.exists(self.AWS_CREDENTIALS_FOLDER):
                os.makedirs(self.AWS_CREDENTIALS_FOLDER)
            # From https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html # noqa: E501
            with open(self.AWS_CREDENTIALS_FILE, 'w') as credentials_file:
                credentials_file.write(
                    '[default]\n' +
                    self.AWS_ACCESS_KEY_ID +
                    ' = ' +
                    self._config[self.CONFIG_AWS_ACCESS_KEY_ID] +
                    '\n' +
                    self.AWS_SECRET_ACCESS_KEY +
                    ' = ' +
                    self._config[self.CONFIG_AWS_SECRET_ACCESS_KEY] +
                    '\n'
                )

        if self.CONFIG_SAVE_IMAGES_TO_S3_BUCKET in self._config:
            if 'boto3' not in sys.modules:
                import boto3
                from botocore.exceptions import ClientError  # noqa: F401
                self.__s3_client = boto3.client('s3')

    def get_seed_value(self):
        return self.__seed

    # Write the history file
    def write_history_file(self, history_string):
        if self.__scene_history_file:
            with open(self.__scene_history_file, "a+") as history_file:
                history_file.write(json.dumps(
                    json.loads(history_string)) + '\n')

    # Override
    def end_scene(self, choice, confidence=1.0):
        """
        Ends the current scene.

        Parameters
        ----------
        choice : string, optional
            The selected choice required for ending scenes with
            violation-of-expectation or classification goals.
            Is not required for other goals. (default None)
        confidence : float, optional
            The choice confidence between 0 and 1 required for ending scenes
            with violation-of-expectation or classification goals.
            Is not required for other goals. (default None)
        """

        super().end_scene(choice, confidence)

        history_item = '{"classification": "' + choice + \
            '", "confidence": ' + str(confidence) + '}'
        self.__history_list.append(history_item)
        self.write_history_file(history_item)

    # Override
    def start_scene(self, config_data):
        """
        Starts a new scene using the given scene configuration data dict and
        returns the scene output data object.

        Parameters
        ----------
        config_data : dict
            The MCS scene configuration data for the scene to start.

        Returns
        -------
        StepMetadata
            The output data object from the start of the scene (the output from
            an "Initialize" action).
        """

        super().start_scene(config_data)

        self.__scene_configuration = config_data
        self.__step_number = 0
        self.__history_list = []
        self._goal = self.retrieve_goal(self.__scene_configuration)
        if 'screenshot' in config_data and config_data['screenshot']:
            self.__scene_history_file = None
        else:
            self.__scene_history_file = os.path.join(
                self.HISTORY_DIRECTORY, config_data['name'].replace(
                    '.json', '') + "-" + self.generate_time() + ".txt")
        skip_preview_phase = (True if 'goal' in config_data and
                              'skip_preview_phase' in config_data['goal']
                              else False)

        if self.__debug_to_file and config_data['name'] is not None:
            os.makedirs('./' + config_data['name'], exist_ok=True)
            self.__output_folder = './' + config_data['name'] + '/'
            file_list = glob.glob(self.__output_folder + '*')
            for file_path in file_list:
                os.remove(file_path)

        output = self.wrap_output(self._controller.step(
            self.wrap_step(action='Initialize', sceneConfig=config_data)))

        if not skip_preview_phase:
            if (self._goal is not None and
                    self._goal.last_preview_phase_step > 0):
                image_list = output.image_list
                depth_mask_list = output.depth_mask_list
                object_mask_list = output.object_mask_list

                if self.__debug_to_terminal:
                    print('STARTING PREVIEW PHASE...')

                for i in range(0, self._goal.last_preview_phase_step):
                    output = self.step('Pass')
                    image_list = image_list + output.image_list
                    depth_mask_list = depth_mask_list + output.depth_mask_list
                    object_mask_list = (object_mask_list +
                                        output.object_mask_list)

                if self.__debug_to_terminal:
                    print('ENDING PREVIEW PHASE')

                output.image_list = image_list
                output.depth_mask_list = depth_mask_list
                output.object_mask_list = object_mask_list
            elif self.__debug_to_terminal:
                print('NO PREVIEW PHASE')

        return output

    # TODO: may need to reevaluate validation strategy/error handling in the
    # future
    """
    Need a validation/conversion step for what ai2thor will accept as input
    to keep parameters more simple for the user (in this case, wrapping
    rotation degrees into an object)
    """

    def validate_and_convert_params(self, action, **kwargs):
        moveMagnitude = MAX_MOVE_DISTANCE
        rotation = kwargs.get(self.ROTATION_KEY, self.DEFAULT_ROTATION)
        horizon = kwargs.get(self.HORIZON_KEY, self.DEFAULT_HORIZON)
        amount = kwargs.get(
            self.AMOUNT_KEY,
            self.DEFAULT_OBJECT_MOVE_AMOUNT
            if action in self.OBJECT_MOVE_ACTIONS
            else self.DEFAULT_AMOUNT
        )
        force = kwargs.get(self.FORCE_KEY, self.DEFAULT_FORCE)

        objectDirectionX = kwargs.get(
            self.OBJECT_DIRECTION_X_KEY, self.DEFAULT_DIRECTION)
        objectDirectionY = kwargs.get(
            self.OBJECT_DIRECTION_Y_KEY, self.DEFAULT_DIRECTION)
        objectDirectionZ = kwargs.get(
            self.OBJECT_DIRECTION_Z_KEY, self.DEFAULT_DIRECTION)
        receptacleObjectDirectionX = kwargs.get(
            self.RECEPTACLE_DIRECTION_X, self.DEFAULT_DIRECTION)
        receptacleObjectDirectionY = kwargs.get(
            self.RECEPTACLE_DIRECTION_Y, self.DEFAULT_DIRECTION)
        receptacleObjectDirectionZ = kwargs.get(
            self.RECEPTACLE_DIRECTION_Z, self.DEFAULT_DIRECTION)

        # Check params that should be numbers
        if not Util.is_number(rotation, self.ROTATION_KEY):
            rotation = self.DEFAULT_ROTATION

        if not Util.is_number(horizon, self.HORIZON_KEY):
            horizon = self.DEFAULT_HORIZON

        if not Util.is_number(amount, self.AMOUNT_KEY):
            # The default for open/close is 1, the default for "Move" actions
            # is 0.5
            if action in self.OBJECT_MOVE_ACTIONS:
                amount = self.DEFAULT_OBJECT_MOVE_AMOUNT
            else:
                amount = self.DEFAULT_AMOUNT

        if not Util.is_number(force, self.FORCE_KEY):
            force = self.DEFAULT_FORCE

        # Check object directions are numbers
        if not Util.is_number(
                objectDirectionX,
                self.OBJECT_DIRECTION_X_KEY):
            objectDirectionX = self.DEFAULT_DIRECTION

        if not Util.is_number(
                objectDirectionY,
                self.OBJECT_DIRECTION_Y_KEY):
            objectDirectionY = self.DEFAULT_DIRECTION

        if not Util.is_number(
                objectDirectionZ,
                self.OBJECT_DIRECTION_Z_KEY):
            objectDirectionZ = self.DEFAULT_DIRECTION

        # Check receptacle directions are numbers
        if not Util.is_number(
                receptacleObjectDirectionX,
                self.RECEPTACLE_DIRECTION_X):
            receptacleObjectDirectionX = self.DEFAULT_DIRECTION

        if not Util.is_number(
                receptacleObjectDirectionY,
                self.RECEPTACLE_DIRECTION_Y):
            receptacleObjectDirectionY = self.DEFAULT_DIRECTION

        if not Util.is_number(
                receptacleObjectDirectionZ,
                self.RECEPTACLE_DIRECTION_Z):
            receptacleObjectDirectionZ = self.DEFAULT_DIRECTION

        # Check that params that should fall in a range are in that range
        horizon = Util.is_in_range(
            horizon,
            self.MIN_HORIZON,
            self.MAX_HORIZON,
            self.DEFAULT_HORIZON,
            self.HORIZON_KEY)
        amount = Util.is_in_range(
            amount,
            self.MIN_AMOUNT,
            self.MAX_AMOUNT,
            self.DEFAULT_AMOUNT,
            self.AMOUNT_KEY)
        force = Util.is_in_range(
            force,
            self.MIN_FORCE,
            self.MAX_FORCE,
            self.DEFAULT_FORCE,
            self.FORCE_KEY)

        # TODO Consider the current "head tilt" value while validating the
        # input "horizon" value.

        # Set the Move Magnitude to the appropriate amount based on the action
        if action in self.FORCE_ACTIONS:
            moveMagnitude = force * self.MAX_BABY_FORCE

        if action in self.OBJECT_MOVE_ACTIONS:
            moveMagnitude = amount

        if action in self.MOVE_ACTIONS:
            moveMagnitude = amount * MAX_MOVE_DISTANCE

        # Add in noise if noise is enable
        if self.__enable_noise:
            rotation = rotation * (1 + self.generate_noise())
            horizon = horizon * (1 + self.generate_noise())
            moveMagnitude = moveMagnitude * (1 + self.generate_noise())

        rotation_vector = {}
        rotation_vector['y'] = rotation

        object_vector = {}
        object_vector['x'] = objectDirectionX
        object_vector['y'] = objectDirectionY
        object_vector['z'] = objectDirectionZ

        receptacle_vector = {}
        receptacle_vector['x'] = receptacleObjectDirectionX
        receptacle_vector['y'] = receptacleObjectDirectionY
        receptacle_vector['z'] = receptacleObjectDirectionZ

        return dict(
            objectId=kwargs.get("objectId", None),
            receptacleObjectId=kwargs.get("receptacleObjectId", None),
            rotation=rotation_vector,
            horizon=horizon,
            moveMagnitude=moveMagnitude,
            objectDirection=object_vector,
            receptacleObjectDirection=receptacle_vector
        )

    # Override
    def step(self, action: str, choice: str = None,
             confidence: float = None,
             violations_xy_list: List[Dict[str, float]] = None,
             heatmap_img: PIL.Image.Image = None,
             internal_state: object = None,
             **kwargs) -> StepMetadata:
        """
        Runs the given action within the current scene and unpauses the scene's
        physics simulation for a few frames. Can also optionally send
        information about scene plausability if applicable.

        Parameters
        ----------
        action : string
            A selected action string from the list of available actions.
        choice : string, optional
            The selected choice required by the end of scenes with
            violation-of-expectation or classification goals.
            Is not required for other goals. (default None)
        confidence : float, optional
            The choice confidence between 0 and 1 required by the end of
            scenes with violation-of-expectation or classification goals.
            Is not required for other goals. (default None)
        violations_xy_list : List[Dict[str, float]], optional
            A list of one or more (x, y) locations (ex: [{"x": 1, "y": 3.4}]),
            each representing a potential violation-of-expectation. Required
            on each step for passive tasks. (default None)
        heatmap_img : PIL.Image.Image, optional
            An image representing scene plausiblility at a particular
            moment. Will be saved as a .png type. (default None)
        internal_state : object, optional
            A properly formatted json object representing various kinds of
            internal states at a particular moment. Examples include the
            estimated position of the agent, current map of the world, etc.
            (default None)
        **kwargs
            Zero or more key-and-value parameters for the action.

        Returns
        -------
        StepMetadata
            The MCS output data object from after the selected action and the
            physics simulation were run. Returns None if you have passed the
            "last_step" of this scene.
        """

        super().step(action, choice, confidence, violations_xy_list,
                     heatmap_img, internal_state, **kwargs)

        if (self._goal.last_step is not None and
                self._goal.last_step == self.__step_number):
            print(
                "MCS Warning: You have passed the last step for this scene. " +
                "Ignoring your action. Please call controller.end_scene() " +
                "now.")
            return None

        if ',' in action:
            action, kwargs = Util.input_to_action_and_params(action)

        action_list = self.retrieve_action_list(self._goal, self.__step_number)
        if action not in action_list:
            print(
                "MCS Warning: The given action '" +
                action +
                "' is not valid. Ignoring your action. " +
                "Please call controller.step() with a valid action.")
            print("Actions (Step " + str(self.__step_number) + "): " +
                  ", ".join(action_list))
            return None

        self.__step_number += 1

        if self.__debug_to_terminal:
            print(
                "================================================"
                "===============================")
            print("STEP: " + str(self.__step_number))
            print("ACTION: " + action)

        params = self.validate_and_convert_params(action, **kwargs)

        # Only call mcs_action_to_ai2thor_action AFTER calling
        # validate_and_convert_params
        action = self.mcs_action_to_ai2thor_action(action)

        if (self._goal.last_step is not None and
                self._goal.last_step == self.__step_number):
            print(
                "MCS Warning: This is your last step for this scene. All " +
                "your future actions will be skipped. Please call " +
                "controller.end_scene() now.")

        output = self.wrap_output(self._controller.step(
            self.wrap_step(action=action, **params)))

        output_copy = copy.deepcopy(output)
        del output_copy.depth_mask_list
        del output_copy.image_list
        del output_copy.object_mask_list
        history_item = SceneHistory(
            step=self.__step_number,
            action=action,
            args=kwargs,
            params=params,
            classification=choice,
            confidence=confidence,
            violations_xy_list=violations_xy_list,
            internal_state=internal_state,
            output=output_copy)
        self.__history_list.append(history_item)
        filtered_history_item = self.filter_history_images(history_item)
        self.write_history_file(str(filtered_history_item))

        if(heatmap_img is not None and
           isinstance(heatmap_img, PIL.Image.Image)):

            team_prefix = (self._config[self.CONFIG_TEAM] +
                           '_') if self.CONFIG_TEAM in self._config else ''
            file_name_prefix = team_prefix + self.HEATMAP_IMAGE_PREFIX + '_'

            self.upload_image_to_s3(heatmap_img, file_name_prefix,
                                    str(self.__step_number))

        return output

    def upload_image_to_s3(self, image_to_upload: PIL.Image.Image,
                           file_name_prefix: str,
                           step_number_affix: str):
        if self.__s3_client:
            in_memory_file = io.BytesIO()
            image_to_upload.save(fp=in_memory_file, format='png')
            in_memory_file.seek(0)
            s3_folder = (
                (self._config[self.CONFIG_SAVE_IMAGES_TO_S3_FOLDER] + '/')
                if self.CONFIG_SAVE_IMAGES_TO_S3_FOLDER in self._config
                else ''
            )
            s3_file_name = s3_folder + file_name_prefix + \
                self.__scene_configuration['name'].replace('.json', '') + \
                '_' + step_number_affix + '_' + \
                self.generate_time() + '.png'
            print('SAVE TO S3 BUCKET ' +
                  self._config[self.CONFIG_SAVE_IMAGES_TO_S3_BUCKET] +
                  ': ' + s3_file_name)
            self.__s3_client.upload_fileobj(
                in_memory_file,
                self._config[self.CONFIG_SAVE_IMAGES_TO_S3_BUCKET],
                s3_file_name,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': 'image/png',
                }
            )

    def filter_history_images(
            self,
            history: SceneHistory) -> SceneHistory:
        if 'target' in history.output.goal.metadata.keys():
            del history.output.goal.metadata['target']['image']
        if 'target_1' in history.output.goal.metadata.keys():
            del history.output.goal.metadata['target_1']['image']
        if 'target_2' in history.output.goal.metadata.keys():
            del history.output.goal.metadata['target_2']['image']
        return history

    def generate_time(self):
        return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    def mcs_action_to_ai2thor_action(self, action):
        if action == Action.CLOSE_OBJECT.value:
            # The AI2-THOR Python library has buggy error checking
            # specifically for the CloseObject action,
            # so just use our own custom action here.
            return "MCSCloseObject"

        if action == Action.DROP_OBJECT.value:
            return "DropHandObject"

        if action == Action.OPEN_OBJECT.value:
            # The AI2-THOR Python library has buggy error checking
            # specifically for the OpenObject action,
            # so just use our own custom action here.
            return "MCSOpenObject"

        # if action == Action.ROTATE_OBJECT_IN_HAND.value:
        #     return "RotateHand"

        return action

    def read_config_file(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r') as config_file:
                config = yaml.load(config_file)
                if self.__debug_to_terminal:
                    print('Read MCS Config File:')
                    print(config)
                if self.CONFIG_METADATA_MODE not in config:
                    config[self.CONFIG_METADATA_MODE] = ''
                return config
        return {}

    def restrict_goal_output_metadata(self, goal_output):
        mode = (
            self._config[self.CONFIG_METADATA_MODE]
            if self.CONFIG_METADATA_MODE in self._config
            else ''
        )

        if (
            mode == self.CONFIG_METADATA_MODE_NO_VISION or
            mode == self.CONFIG_METADATA_MODE_NONE
        ):
            if (
                'target' in goal_output.metadata and
                'image' in goal_output.metadata['target']
            ):
                goal_output.metadata['target']['image'] = None
            if (
                'target_1' in goal_output.metadata and
                'image' in goal_output.metadata['target_1']
            ):
                goal_output.metadata['target_1']['image'] = None
            if (
                'target_2' in goal_output.metadata and
                'image' in goal_output.metadata['target_2']
            ):
                goal_output.metadata['target_2']['image'] = None

        return goal_output

    def restrict_object_output_metadata(self, object_output):
        mode = (
            self._config[self.CONFIG_METADATA_MODE]
            if self.CONFIG_METADATA_MODE in self._config
            else ''
        )

        if (
            mode == self.CONFIG_METADATA_MODE_NO_VISION or
            mode == self.CONFIG_METADATA_MODE_NONE
        ):
            object_output.color = None
            object_output.dimensions = None
            object_output.direction = None
            object_output.distance = None
            object_output.distance_in_steps = None
            object_output.distance_in_world = None
            object_output.shape = None
            object_output.texture_color_list = None

        if (
            mode == self.CONFIG_METADATA_MODE_NO_NAVIGATION or
            mode == self.CONFIG_METADATA_MODE_NONE
        ):
            object_output.position = None
            object_output.rotation = None

        return object_output

    def restrict_step_output_metadata(self, step_output):
        mode = (
            self._config[self.CONFIG_METADATA_MODE]
            if self.CONFIG_METADATA_MODE in self._config
            else ''
        )

        if (
            mode == self.CONFIG_METADATA_MODE_NO_VISION or
            mode == self.CONFIG_METADATA_MODE_NONE
        ):
            step_output.camera_aspect_ratio = None
            step_output.camera_clipping_planes = None
            step_output.camera_field_of_view = None
            step_output.camera_height = None
            step_output.depth_mask_list = []
            step_output.object_mask_list = []

        if (
            mode == self.CONFIG_METADATA_MODE_NO_NAVIGATION or
            mode == self.CONFIG_METADATA_MODE_NONE
        ):
            step_output.position = None
            step_output.rotation = None

        return step_output

    def retrieve_action_list(self, goal, step_number):
        if goal is not None and goal.action_list is not None:
            if step_number < goal.last_preview_phase_step:
                return ['Pass']
            adjusted_step = step_number - goal.last_preview_phase_step
            if len(goal.action_list) > adjusted_step:
                if len(goal.action_list[adjusted_step]) > 0:
                    return goal.action_list[adjusted_step]

        return self.ACTION_LIST

    def retrieve_goal(self, scene_configuration):
        goal_config = (
            scene_configuration['goal']
            if 'goal' in scene_configuration
            else {}
        )

        if 'category' in goal_config:
            # Backwards compatibility
            goal_config['metadata']['category'] = goal_config['category']

        return self.restrict_goal_output_metadata(GoalMetadata(
            action_list=(goal_config['action_list']
                         if 'action_list' in goal_config else None),
            category=(goal_config['category']
                      if 'category' in goal_config else ''),
            description=(goal_config['description']
                         if 'description' in goal_config else ''),
            domain_list=(goal_config['domain_list']
                         if 'domain_list' in goal_config else []),
            info_list=(goal_config['info_list']
                       if 'type_list' in goal_config else []),
            last_preview_phase_step=(
                goal_config['last_preview_phase_step']
                if 'last_preview_phase_step' in goal_config
                else 0
            ),
            last_step=(goal_config['last_step']
                       if 'last_step' in goal_config else None),
            type_list=(goal_config['type_list']
                       if 'type_list' in goal_config else []),
            metadata=(goal_config['metadata']
                      if 'metadata' in goal_config else {})
        ))

    def retrieve_head_tilt(self, scene_event):
        return scene_event.metadata['agent']['cameraHorizon']

    def retrieve_rotation(self, scene_event):
        return scene_event.metadata['agent']['rotation']['y']

    def retrieve_object_colors(self, scene_event):
        # Use the color map for the final event (though they should all be the
        # same anyway).
        return scene_event.events[len(
            scene_event.events) - 1].object_id_to_color

    def retrieve_object_list(self, scene_event):
        mode = (
            self._config[self.CONFIG_METADATA_MODE]
            if self.CONFIG_METADATA_MODE in self._config
            else ''
        )

        if mode == self.CONFIG_METADATA_MODE_FULL:
            return sorted(
                [
                    self.retrieve_object_output(
                        object_metadata,
                        self.retrieve_object_colors(scene_event),
                    )
                    for object_metadata in scene_event.metadata['objects']
                ],
                key=lambda x: x.uuid
            )

        return sorted(
            [
                self.retrieve_object_output(
                    object_metadata, self.retrieve_object_colors(scene_event)
                )
                for object_metadata in scene_event.metadata['objects']
                if object_metadata['visibleInCamera'] or
                object_metadata['isPickedUp']
            ],
            key=lambda x: x.uuid
        )

    def retrieve_object_output(self, object_metadata, object_id_to_color):
        material_list = (
            list(
                filter(
                    Util.verify_material_enum_string,
                    [
                        material.upper()
                        for material in object_metadata['salientMaterials']
                    ],
                )
            )
            if object_metadata['salientMaterials'] is not None
            else []
        )

        rgb = (
            object_id_to_color[object_metadata['objectId']]
            if object_metadata['objectId'] in object_id_to_color
            else [None, None, None]
        )

        bounds = (
            object_metadata['objectBounds']
            if 'objectBounds' in object_metadata and
            object_metadata['objectBounds'] is not None
            else {}
        )

        return self.restrict_object_output_metadata(
            ObjectMetadata(
                uuid=object_metadata['objectId'],
                color={'r': rgb[0], 'g': rgb[1], 'b': rgb[2]},
                dimensions=(
                    bounds['objectBoundsCorners']
                    if 'objectBoundsCorners' in bounds
                    else None
                ),
                direction=object_metadata['direction'],
                distance=(
                    object_metadata['distanceXZ'] / MAX_MOVE_DISTANCE
                ),  # DEPRECATED
                distance_in_steps=(
                    object_metadata['distanceXZ'] / MAX_MOVE_DISTANCE
                ),
                distance_in_world=(object_metadata['distance']),
                held=object_metadata['isPickedUp'],
                mass=object_metadata['mass'],
                material_list=material_list,
                position=object_metadata['position'],
                rotation=object_metadata['rotation'],
                shape=object_metadata['shape'],
                texture_color_list=object_metadata['colorsFromMaterials'],
                visible=(
                    object_metadata['visibleInCamera'] or
                    object_metadata['isPickedUp']
                ),
            )
        )

    def retrieve_pose(self, scene_event) -> str:
        pose = Pose.UNDEFINED.name

        try:
            pose = Pose[scene_event.metadata['pose']].name
        except KeyError:
            print(
                "Pose " +
                scene_event.metadata['pose'] +
                " is not currently supported.")
        finally:
            return pose

    def retrieve_position(self, scene_event) -> dict:
        return scene_event.metadata['agent']['position']

    def retrieve_return_status(self, scene_event):
        # TODO MCS-47 Need to implement all proper step statuses on the Unity
        # side
        return_status = ReturnStatus.UNDEFINED.name

        try:
            if scene_event.metadata['lastActionStatus']:
                return_status = ReturnStatus[
                    scene_event.metadata['lastActionStatus']
                ].name
        except KeyError:
            print(
                "Return status " +
                scene_event.metadata['lastActionStatus'] +
                " is not currently supported.")
        finally:
            return return_status

    def retrieve_structural_object_list(self, scene_event):
        mode = (
            self._config[self.CONFIG_METADATA_MODE]
            if self.CONFIG_METADATA_MODE in self._config
            else ''
        )

        if mode == self.CONFIG_METADATA_MODE_FULL:
            return sorted(
                [
                    self.retrieve_object_output(
                        object_metadata,
                        self.retrieve_object_colors(scene_event),
                    )
                    for object_metadata in scene_event.metadata[
                        'structuralObjects'
                    ]
                ],
                key=lambda x: x.uuid
            )

        return sorted(
            [
                self.retrieve_object_output(
                    object_metadata, self.retrieve_object_colors(scene_event)
                )
                for object_metadata in scene_event.metadata[
                    'structuralObjects'
                ]
                if object_metadata['visibleInCamera']
            ],
            key=lambda x: x.uuid
        )

    def save_images(self, scene_event):
        image_list = []
        depth_mask_list = []
        object_mask_list = []

        for index, event in enumerate(scene_event.events):
            scene_image = PIL.Image.fromarray(event.frame)
            image_list.append(scene_image)

            if self.__depth_masks:
                depth_mask = PIL.Image.fromarray(event.depth_frame)
                depth_mask = depth_mask.convert('L')
                depth_mask_list.append(depth_mask)

            if self.__object_masks:
                object_mask = PIL.Image.fromarray(
                    event.instance_segmentation_frame)
                object_mask_list.append(object_mask)

            if self.__debug_to_file and self.__output_folder is not None:
                step_plus_substep_index = 0 if self.__step_number == 0 else (
                    (self.__step_number - 1) * 5) + (index + 1)
                suffix = '_' + str(step_plus_substep_index) + '.png'
                scene_image.save(fp=self.__output_folder +
                                 'frame_image' + suffix)
                if self.__depth_masks:
                    depth_mask.save(fp=self.__output_folder +
                                    'depth_mask' + suffix)
                if self.__object_masks:
                    object_mask.save(fp=self.__output_folder +
                                     'object_mask' + suffix)

            team_prefix = (self._config[self.CONFIG_TEAM] +
                           '_') if self.CONFIG_TEAM in self._config else ''
            step_num_affix = (str(self.__step_number) + '_' +
                              str(index + 1))

            self.upload_image_to_s3(scene_image, team_prefix,
                                    step_num_affix)

        return image_list, depth_mask_list, object_mask_list

    def wrap_output(self, scene_event):
        if self.__debug_to_file and self.__output_folder is not None:
            with open(self.__output_folder + 'ai2thor_output_' +
                      str(self.__step_number) + '.json', 'w') as json_file:
                json.dump({
                    "metadata": scene_event.metadata
                }, json_file, sort_keys=True, indent=4)

        image_list, depth_mask_list, object_mask_list = self.save_images(
            scene_event)

        objects = scene_event.metadata.get('objects', None)
        agent = scene_event.metadata.get('agent', None)
        step_output = self.restrict_step_output_metadata(StepMetadata(
            action_list=self.retrieve_action_list(
                self._goal, self.__step_number),
            camera_aspect_ratio=(self.__screen_width, self.__screen_height),
            camera_clipping_planes=(
                scene_event.metadata.get('clippingPlaneNear', 0.0),
                scene_event.metadata.get('clippingPlaneFar', 0.0),
            ),
            camera_field_of_view=scene_event.metadata.get('fov', 0.0),
            camera_height=scene_event.metadata.get(
                'cameraPosition', {}).get('y', 0.0),
            depth_mask_list=depth_mask_list,
            goal=self._goal,
            head_tilt=self.retrieve_head_tilt(scene_event),
            image_list=image_list,
            object_list=self.retrieve_object_list(scene_event),
            object_mask_list=object_mask_list,
            pose=self.retrieve_pose(scene_event),
            position=self.retrieve_position(scene_event),
            return_status=self.retrieve_return_status(scene_event),
            reward=Reward.calculate_reward(self._goal, objects, agent),
            rotation=self.retrieve_rotation(scene_event),
            step_number=self.__step_number,
            structural_object_list=self.retrieve_structural_object_list(
                scene_event)
        ))

        self.__head_tilt = step_output.head_tilt

        if self.__debug_to_terminal:
            print("RETURN STATUS: " + step_output.return_status)
            print("OBJECTS: " + str(len(step_output.object_list)) + " TOTAL")
            if len(step_output.object_list) > 0:
                for line in Util.generate_pretty_object_output(
                        step_output.object_list):
                    print("    " + line)

        if self.__debug_to_file and self.__output_folder is not None:
            with open(self.__output_folder + 'mcs_output_' +
                      str(self.__step_number) + '.json', 'w') as json_file:
                json_file.write(str(step_output))

        return step_output

    def wrap_step(self, **kwargs):
        # Create the step data dict for the AI2-THOR step function.
        step_data = dict(
            continuous=True,
            gridSize=self.GRID_SIZE,
            logs=True,
            renderDepthImage=self.__depth_masks,
            renderObjectImage=self.__object_masks,
            # Yes, in AI2-THOR, the player's reach appears to be
            # governed by the "visibilityDistance", confusingly...
            visibilityDistance=MAX_REACH_DISTANCE,
            **kwargs
        )

        if self.__debug_to_file and self.__output_folder is not None:
            with open(self.__output_folder + 'ai2thor_input_' +
                      str(self.__step_number) + '.json', 'w') as json_file:
                json.dump(step_data, json_file, sort_keys=True, indent=4)

        return step_data