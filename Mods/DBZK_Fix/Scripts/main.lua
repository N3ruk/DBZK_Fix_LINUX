---@diagnostic disable: undefined-global

-- ============================================================
-- DBZK_Fix_LINUX v0.4.1
--
-- Based on DBZK_Fix by Bryce Q. / KingKrouch
-- Original project licensed under the MIT License.
--
-- Linux / Proton compatibility fork:
-- https://github.com/neruk123-droid/DBZK_Fix_LINUX
--
-- Changes in this fork:
--   - Deferred Unreal Engine object initialization
--   - Safer UObject validation
--   - Steam Deck / Proton crash fix
--   - Corrected UE4SS FOV hook handling
--   - Safe game-thread execution
--   - Modular feature switches
-- ============================================================

local version = "0.4.1-linux"

local UEHelpers = require("UEHelpers")
local inifile = require("inifile")

-- ============================================================
-- FEATURE SWITCHES
-- ============================================================

local ENABLE_FPS_UNLOCK          = true
local ENABLE_RUNTIME_SETTINGS    = true
local ENABLE_LOCALPLAYER_ASPECT  = true
local ENABLE_CAMERA_ASPECT       = true
local ENABLE_FOV_HOOK            = true
local ENABLE_CUTSCENE_REAPPLY    = true

-- ============================================================
-- STATE / CONFIG
-- ============================================================

local init = false

---@type boolean
local showFPSStats = false

---@type boolean
local useTemporalUpscaling = false

---@type boolean
local useMotionBlur = true

---@type integer
local fpsCap = 0

---@type boolean
local useFixedFrameRate = false

---@type integer
local vsyncInterval = 1

---@type number
local ogAspectRatio = 16 / 9

---@type boolean
local verbose = false

---@type UObject
local currentCheatManager = nil

-- ============================================================
-- LOGGING
-- ============================================================

---@param line string
function LogPrint(line)
print("[DBZK_Fix] " .. tostring(line) .. "\n")
end

---@param line string
function LogError(line)
print("[DBZK_Fix] ERROR: " .. tostring(line) .. "\n")
end

---@param line string
function LogDebug(line)
if verbose then
    print("[DBZK_Fix] DEBUG: " .. tostring(line) .. "\n")
    end
    end

    -- ============================================================
    -- SAFETY HELPERS
    -- ============================================================

    ---@param obj UObject
    ---@return boolean
    function SafeIsValid(obj)
    if obj == nil then
        return false
        end

        local ok, result = pcall(function()
        return obj:IsValid()
        end)

        if not ok then
            LogError("Exception while checking UObject validity: " .. tostring(result))
            return false
            end

            return result == true
            end

            ---@param label string
            ---@param callback function
            ---@return boolean
            function RunProtected(label, callback)
            local ok, err = pcall(callback)

            if not ok then
                LogError(label .. " failed: " .. tostring(err))
                return false
                end

                return true
                end

                -- ============================================================
                -- CONFIG
                -- ============================================================

                function Init()
                if init then
                    return true
                    end

                    LogPrint("Initializing DBZK_Fix " .. version)

                    local ok, config = pcall(function()
                    return inifile.parse("Config.ini")
                    end)

                    if not ok or config == nil then
                        LogError("Unable to read Config.ini")
                        return false
                        end

                        local misc = config["Misc"] or {}
                        local graphics = config["Graphics"] or {}
                        local framerate = config["Framerate"] or {}

                        showFPSStats = misc["ShowFPSStats"]
                        if showFPSStats == nil then
                            showFPSStats = false
                            end

                            useTemporalUpscaling = graphics["TemporalUpscaling"]
                            if useTemporalUpscaling == nil then
                                useTemporalUpscaling = false
                                end

                                useMotionBlur = graphics["MotionBlur"]
                                if useMotionBlur == nil then
                                    useMotionBlur = true
                                    end

                                    vsyncInterval = framerate["VSyncInterval"]
                                    if vsyncInterval == nil then
                                        vsyncInterval = 1
                                        end

                                        local fpsCapCheck = framerate["MaxFPS"]
                                        if fpsCapCheck == nil then
                                            LogError("Missing MaxFPS in [Framerate]")
                                            return false
                                            end

                                            useFixedFrameRate = framerate["UseFixed"]
                                            if useFixedFrameRate == nil then
                                                useFixedFrameRate = false
                                                end

                                                -- Original DBZK_Fix behaviour:
                                                -- MaxFPS=0 maps to 9999 because literal 0 can have side effects.
                                                if fpsCapCheck == 0 then
                                                    fpsCap = 9999
                                                    else
                                                        fpsCap = fpsCapCheck
                                                        end

                                                        init = true

                                                        LogPrint("Configuration loaded")
                                                        LogPrint("FPS target: " .. tostring(fpsCap))
                                                        LogPrint("Fixed frame rate: " .. tostring(useFixedFrameRate))
                                                        LogDebug("VSync interval: " .. tostring(vsyncInterval))
                                                        LogDebug("Temporal upscaling: " .. tostring(useTemporalUpscaling))
                                                        LogDebug("Motion blur: " .. tostring(useMotionBlur))
                                                        LogDebug("FPS stats: " .. tostring(showFPSStats))

                                                        return true
                                                        end

                                                        -- ============================================================
                                                        -- FPS UNLOCK
                                                        -- ============================================================

                                                        ---@param fps integer
                                                        ---@return boolean
                                                        function UncapFPS(fps)
                                                        if not ENABLE_FPS_UNLOCK then
                                                            return true
                                                            end

                                                            LogDebug("UncapFPS() requested: " .. tostring(fps))

                                                            if currentCheatManager == nil then
                                                                LogDebug("No current ATCheatManager yet")
                                                                return false
                                                                end

                                                                if not SafeIsValid(currentCheatManager) then
                                                                    LogError("currentCheatManager is invalid")
                                                                    currentCheatManager = nil
                                                                    return false
                                                                    end

                                                                    if useFixedFrameRate then
                                                                        LogDebug("Calling ATFrameRateFixed(" .. tostring(fps) .. ")")

                                                                        local ok = RunProtected("ATFrameRateFixed", function()
                                                                        currentCheatManager:ATFrameRateFixed(fps)
                                                                        end)

                                                                        if ok then
                                                                            LogPrint("ATFrameRateFixed applied: " .. tostring(fps))
                                                                            end

                                                                            return ok
                                                                            else
                                                                                LogDebug("Calling ATFrameRateVariable(" .. tostring(fps) .. ")")

                                                                                local ok = RunProtected("ATFrameRateVariable", function()
                                                                                currentCheatManager:ATFrameRateVariable(fps)
                                                                                end)

                                                                                if ok then
                                                                                    LogPrint("ATFrameRateVariable applied: " .. tostring(fps))
                                                                                    end

                                                                                    return ok
                                                                                    end
                                                                                    end

                                                                                    -- ============================================================
                                                                                    -- CONSOLE COMMANDS / GRAPHICS SETTINGS
                                                                                    -- ============================================================

                                                                                    ---@param cmd string
                                                                                    ---@return boolean
                                                                                    function ExecCmdNow(cmd)
                                                                                    local ksl = nil
                                                                                    local worldContext = nil

                                                                                    local okKsl = RunProtected("GetKismetSystemLibrary", function()
                                                                                    ksl = UEHelpers.GetKismetSystemLibrary()
                                                                                    end)

                                                                                    if not okKsl or not SafeIsValid(ksl) then
                                                                                        LogError("KismetSystemLibrary is not valid for command: " .. tostring(cmd))
                                                                                        return false
                                                                                        end

                                                                                        local okWorld = RunProtected("GetWorldContextObject", function()
                                                                                        worldContext = UEHelpers:GetWorldContextObject()
                                                                                        end)

                                                                                        if not okWorld or not SafeIsValid(worldContext) then
                                                                                            LogError("WorldContextObject is not valid for command: " .. tostring(cmd))
                                                                                            return false
                                                                                            end

                                                                                            LogDebug("ExecCmd: " .. tostring(cmd))

                                                                                            return RunProtected("ExecuteConsoleCommand: " .. tostring(cmd), function()
                                                                                            ksl:ExecuteConsoleCommand(worldContext, cmd, nil)
                                                                                            end)
                                                                                            end

                                                                                            ---@param callback function
                                                                                            ---@param label string
                                                                                            function QueueGameThread(callback, label)
                                                                                            label = label or "game-thread task"

                                                                                            local ok, err = pcall(function()
                                                                                            ExecuteInGameThread(function()
                                                                                            local success, callbackErr = pcall(callback)

                                                                                            if not success then
                                                                                                LogError(label .. " callback failed: " .. tostring(callbackErr))
                                                                                                end
                                                                                                end)
                                                                                            end)

                                                                                            if not ok then
                                                                                                -- Fallback: if ExecuteInGameThread is unavailable for some reason,
-- run protected in the current callback instead of killing the mod.
LogError("ExecuteInGameThread failed for " .. label .. ": " .. tostring(err))
RunProtected(label .. " fallback", callback)
end
end

---@param reason string
function ApplyRuntimeSettings(reason)
if not ENABLE_RUNTIME_SETTINGS then
    return
    end

    reason = reason or "unspecified"
    LogDebug("Applying runtime settings (" .. reason .. ")")

    QueueGameThread(function()
    ExecCmdNow("rhi.SyncInterval " .. tostring(vsyncInterval))

    if useTemporalUpscaling then
        ExecCmdNow("r.DefaultFeature.AntiAliasing 2")
        ExecCmdNow("r.PostProcessAAQuality 6")
        ExecCmdNow("r.TemporalAA.Upsampling 1")
        ExecCmdNow("r.TemporalAA.Algorithm 1")
        end

        if not useMotionBlur then
            ExecCmdNow("r.MotionBlurQuality 0")
            end

            if showFPSStats then
                ExecCmdNow("stat detailed")
                end
                end, "ApplyRuntimeSettings")
    end

    ---@param reason string
    function ReapplyGameFixes(reason)
    reason = reason or "unspecified"

    LogDebug("Reapplying fixes (" .. reason .. ")")

    if ENABLE_FPS_UNLOCK then
        UncapFPS(fpsCap)
        end

        if ENABLE_RUNTIME_SETTINGS then
            ApplyRuntimeSettings(reason)
            end
            end

            -- ============================================================
            -- FOV HELPERS
            -- ============================================================

            ---@param hfov number
            ---@param aspect_ratio number
            ---@return number
            function HFOV_to_VFOV(hfov, aspect_ratio)
            local hfov_radians = math.rad(hfov / 2)
            local vfov_radians = 2 * math.atan(math.tan(hfov_radians) / aspect_ratio)
            return math.deg(vfov_radians)
            end

            ---@param vfov number
            ---@param aspect_ratio number
            ---@return number
            function VFOV_TO_HFOV(vfov, aspect_ratio)
            local vfov_radians = math.rad(vfov / 2)
            local hfov_radians = 2 * math.atan(aspect_ratio * math.tan(vfov_radians))
            return math.deg(hfov_radians)
            end

            -- ============================================================
            -- START
            -- ============================================================

            if not Init() then
                LogError("Initialization failed; DBZK_Fix will not register callbacks")
                return
                end

                LogPrint("Safe startup complete; waiting for Unreal objects")

                -- ============================================================
                -- LOCAL PLAYER ASPECT-RATIO BEHAVIOUR
                -- ============================================================

                if ENABLE_LOCALPLAYER_ASPECT then
                    NotifyOnNewObject("/Script/Engine.LocalPlayer",
                                      function(CreatedObject)
                                      if not SafeIsValid(CreatedObject) then
                                          LogError("Invalid LocalPlayer received")
                                          return
                                          end

                                          RunProtected("LocalPlayer AspectRatioAxisConstraint", function()
                                          -- AspectRatio_MaintainYFOV
                                          CreatedObject.AspectRatioAxisConstraint = 0
                                          end)

                                          LogDebug("Patched LocalPlayer AspectRatioAxisConstraint")
                                          end)
                    end

                    -- ============================================================
                    -- CAMERA ASPECT-RATIO CONSTRAINT
                    --
                    -- The generic CameraComponent notification also covers the title-screen
                    -- CameraComponents, so we do not register redundant object-specific
                    -- notifications for CameraActor_0 / CameraActor_1.
                    -- ============================================================

                    if ENABLE_CAMERA_ASPECT then
                        NotifyOnNewObject("/Script/Engine.CameraComponent",
                                          function(CreatedObject)
                                          if not SafeIsValid(CreatedObject) then
                                              return
                                              end

                                              RunProtected("CameraComponent bConstrainAspectRatio", function()
                                              CreatedObject.bConstrainAspectRatio = false
                                              end)

                                              LogDebug("Patched CameraComponent bConstrainAspectRatio")
                                              end)
                        end

                        -- ============================================================
                        -- FOV HOOK
                        --
                        -- RegisterHook callbacks receive Context first, then the function
                        -- parameters as RemoteUnrealParam wrappers. The original mod treated
                        -- the first callback argument as the FOV value; here we unwrap/set the
                        -- actual InFieldOfView parameter correctly.
                        -- ============================================================

                        if ENABLE_FOV_HOOK then
                            local hookOk, hookErr = pcall(function()
                            RegisterHook(
                                "/Script/Engine.CameraComponent:SetFieldOfView",
                                function(Context, InFieldOfView)
                                local ok, err = pcall(function()
                                local camera = Context:get()

                                if not SafeIsValid(camera) then
                                    return
                                    end

                                    if InFieldOfView == nil then
                                        return
                                        end

                                        local fovOld = InFieldOfView:get()

                                        if type(fovOld) ~= "number" then
                                            LogError("SetFieldOfView received non-numeric FOV")
                                            return
                                            end

                                            local newFov = HFOV_to_VFOV(fovOld, ogAspectRatio)

                                            InFieldOfView:set(newFov)

                                            LogDebug(
                                                "FOV adjusted: "
                                                .. tostring(fovOld)
                                                .. " -> "
                                                .. tostring(newFov)
                                            )
                                            end)

                                if not ok then
                                    LogError("SetFieldOfView hook callback failed: " .. tostring(err))
                                    end
                                    end
                            )
                            end)

                            if hookOk then
                                LogPrint("SetFieldOfView hook registered")
                                else
                                    LogError("Unable to register SetFieldOfView hook: " .. tostring(hookErr))
                                    end
                                    end

                                    -- ============================================================
                                    -- CHEAT MANAGER / FPS
                                    -- ============================================================

                                    NotifyOnNewObject("/Script/AT.ATCheatManager",
                                                      function(CreatedObject)
                                                      LogDebug("ATCheatManager creation notification received")

                                                      if not SafeIsValid(CreatedObject) then
                                                          LogError("Invalid ATCheatManager created")
                                                          return
                                                          end

                                                          currentCheatManager = CreatedObject
                                                          LogPrint("Valid ATCheatManager found")

                                                          ReapplyGameFixes("ATCheatManager created")
                                                          end)

                                    -- ============================================================
                                    -- CUTSCENES
                                    --
                                    -- The original mod called Fix() whenever these objects appeared.
                                    -- We keep that behaviour, but only after validating the object and
                                    -- through the safe reapply path instead of the old startup Fix().
                                    -- ============================================================

                                    if ENABLE_CUTSCENE_REAPPLY then
                                        NotifyOnNewObject("/Script/ATExt.ATSceneEvent",
                                                          function(CreatedObject)
                                                          if not SafeIsValid(CreatedObject) then
                                                              return
                                                              end

                                                              LogDebug("ATSceneEvent created")
                                                              ReapplyGameFixes("ATSceneEvent")
                                                              end)

                                        NotifyOnNewObject("/Script/ATExt.ATSceneDemoBase",
                                                          function(CreatedObject)
                                                          if not SafeIsValid(CreatedObject) then
                                                              return
                                                              end

                                                              LogDebug("ATSceneDemoBase created")
                                                              ReapplyGameFixes("ATSceneDemoBase")
                                                              end)
                                        end

                                        LogPrint("All enabled DBZK_Fix callbacks registered")
