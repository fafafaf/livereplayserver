# by "o" Posted: 22 Mar, 2007 on GPG forum: http://forums.gaspowered.com/viewtopic.php?p=64594#p64594

# Format of command stream:
#
# repeat {
#   uint8 - message typecode (ECmdStreamOp)
#   uint16 - length of message (including header)
#   ... - op specific data
# }

class ECmdStreamOp:
    (
        CMDST_Advance,
        # uint32 - number of beats to advance.

        CMDST_SetCommandSource,
        # uint8 - command source

        CMDST_CommandSourceTerminated,
        # no args.

        CMDST_VerifyChecksum,
        # MD5Digest - checksum
        # uint32 - beat number

        CMDST_RequestPause,
        CMDST_Resume,
        CMDST_SingleStep,
        # All with no additional data.

        CMDST_CreateUnit,
        # uint8 - army index
        # string - blueprint ID
        # float - x
        # float - z
        # float - heading

        CMDST_CreateProp,
        # string - blueprint ID
        # Vector3f - location

        CMDST_DestroyEntity,
        # EntId - entity

        CMDST_WarpEntity,
        # EntId - entity
        # VTransform - new transform

        CMDST_ProcessInfoPair,
        # EntId - entity
        # string - arg1
        # string - arg2

        CMDST_IssueCommand,
        # uint32 - num units
        # EntIdSet - units
        # CmdData - command data
        # uint8 - clear queue flag

        CMDST_IssueFactoryCommand,
        # uint32 - num factories
        # EntIdSet - factories
        # CmdData - command data
        # uint8 - clear queue flag

        CMDST_IncreaseCommandCount,
        # CmdId - command id
        # int32 - count delta

        CMDST_DecreaseCommandCount,
        # CmdId - command id
        # int32 - count delta

        CMDST_SetCommandTarget,
        # CmdId - command id
        # STITarget - target

        CMDST_SetCommandType,
        # CmdId - command id
        # EUnitCommandType - type


        CMDST_SetCommandCells,
        # CmdId - command id
        # ListOfCells - list of cells
        # Vector3f - pos

        CMDST_RemoveCommandFromQueue,
        # CmdId - command id
        # EntId - unit

        CMDST_DebugCommand,
        # string -- the debug command string
        # Vector3f -- mouse pos (in world coords)
        # uint8 -- focus army index
        # EntIdSet -- selection

        CMDST_ExecuteLuaInSim,
        # string -- the lua string to evaluate in the sim state

        CMDST_LuaSimCallback,
        # string - callback function name
        # LuaObject - table of function arguments

        CMDST_EndGame,
        # no args.
    ) = range(24)
    
# Format of EntIdSet:
#
# uint32 - number of entity ids
# repeat number of entity ids times {
#   EndId - entity id
# }


# Format of CmdData:
#
# CmdId - id
# uint8 - command type (EUnitCommandType)
# STITarget - target
# int32 - formation index or -1
# if formation index != -1
# {
#   Quaternionf - formation orientation
#   float - formation scale
# }
# string - blueprint ID or the empty string for no blueprint
# ListOfCells - cells
# int32 - count


# Format of STITarget:
#
# uint8 - target type (ESTITargetType)
# if target type == STITARGET_Entity {
#   EntId - entity id
# }
# if target type == STITARGET_Position {
#   Vector3f - position
# }


# Format of ListOfCells:
#
# uint32 - num cells
# repeat num cells times {
#   int16 - x
#   int16 - z
# }

# this is guessing from FA.exe

class EUnitCommandType:
    (
        NONE,
        Stop,
        Move,
        Dive,
        FormMove,
        BuildSiloTactical,
        BuildSiloNuke,
        BuildFactory,
        BuildMobile,
        BuildAssist,
        Attack,
        FormAttack,
        Nuke,
        Tactical,
        Teleport,
        Guard,
        Patrol,
        Ferry,
        FormPatrol,
        Reclaim,
        Repair,
        Capture,
        TransportLoadUnits,
        TransportReverseLoadUnits,
        TransportUnloadUnits,
        TransportUnloadSpecificUnits,
        DetachFromTransport,
        Upgrade,
        Script,
        AssistCommander,
        KillSelf,
        DestroySelf,
        Sacrifice,
        Pause,
        OverCharge,
        AggressiveMove,
        FormAggressiveMove,
        AssistMove,
        SpecialAction,
        Dock,
    ) = range(40)

class STITARGET:
    (
        NONE,
        Entity,
        Position
    ) = range(3)


class LUA_TYPE:
    (
        NUMBER,
        STRING,
        NIL,
        BOOL,
        LUA,
        LUA_END,
    ) = range(6)


cmdTypeToString = [
    "NONE",
    "Stop",
    "Move",
    "Dive",
    "FormMove",
    "BuildSiloTactical",
    "BuildSiloNuke",
    "BuildMobile",
    "BuildFactory",
    "BuildAssist",
    "Attack",
    "FormAttack",
    "Nuke",
    "Tactical",
    "Teleport",
    "Guard",
    "Patrol",
    "Ferry",
    "FormPatrol",
    "Reclaim",
    "Repair",
    "Capture",
    "TransportLoadUnits",
    "TransportReverseLoadUnits",
    "TransportUnloadUnits",
    "TransportUnloadSpecificUnits",
    "DetachFromTransport",
    "Upgrade",
    "Script",
    "AssistCommander",
    "KillSelf",
    "DestroySelf",
    "Sacrifice",
    "Pause",
    "OverCharge",
    "AggressiveMove",
    "FormAggressiveMove",
    "AssistMove",
    "SpecialAction",
    "Dock"
]