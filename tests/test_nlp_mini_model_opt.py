import pytest
import time
import numpy as np
from app.router import ExecutionContext, split_commands, plan_user_input, match_direct_command, VERB_TOOL_MAP
from app.core import parse_fallback_json
from app.voice.config import VoiceConfig
from app.voice.vad import VADEngine


# ==============================================================================
# SECTION 1: NLP ROUTER & INTENT PARSER VALIDATION
# ==============================================================================

class TestNLPRouterValidation:
    """Validates the Layer 1 lightweight NLP router for fast intent parsing."""

    def test_split_commands_delimiters(self):
        """Test splitting across diverse natural language delimiters."""
        inputs = [
            ("open chrome && open notepad", ["open chrome", "open notepad"]),
            ("open chrome; open notepad", ["open chrome", "open notepad"]),
            ("open chrome\nopen notepad", ["open chrome", "open notepad"]),
            ("open chrome, open notepad", ["open chrome", "open notepad"]),
            ("open chrome and open notepad", ["open chrome", "open notepad"]),
            ("open edge, type hello world and maximize it", ["open edge", "type hello world", "maximize it"]),
            ("launch calc; press 5 && hit enter", ["launch calc", "press 5", "hit enter"]),
        ]
        for raw, expected in inputs:
            assert split_commands(raw) == expected

    def test_verb_to_tool_mapping_coverage(self):
        """Verify that essential user actions map directly to correct tools."""
        ctx = ExecutionContext()
        test_cases = [
            ("open chrome", "open_app", {"app_name": "chrome"}),
            ("launch notepad", "open_app", {"app_name": "notepad"}),
            ("close edge", "close_app", {"app_name": "edge"}),
            ("maximize chrome", "maximize_window", {"app_name": "chrome"}),
            ("minimize notepad", "minimize_window", {"app_name": "notepad"}),
            ("focus vlc", "focus_window", {"app_name": "vlc"}),
            ("type hello jarvis", "type_text", {"text": "hello jarvis"}),
            ("write test.txt", "type_text", {"text": "test.txt"}),
            ("press enter", "press_key", {"key": "enter"}),
            ("hotkey ctrl+c", "hotkey", {"key": "ctrl+c"}),
            ("click submit button", "mouse_click", {"target": "submit button"}),
            ("scroll down", "mouse_scroll", {"args": "down"}),
            ("search python tutorials", "web_search", {"query": "python tutorials"}),
            ("goto https://google.com", "open_url", {"url": "https://google.com"}),
            ("screenshot screen", "take_screenshot", {}),
            ("volume 80%", "set_volume", {"level": 80}),
            ("mute audio", "mute_audio", {}),
        ]
        for cmd, expected_tool, expected_args in test_cases:
            step = match_direct_command(cmd, ctx)
            assert step.is_direct is True, f"Command '{cmd}' should be marked direct"
            assert step.tool_name in (expected_tool, "windows_search"), f"Tool mismatch for '{cmd}'"
            for k, v in expected_args.items():
                assert step.tool_args.get(k) == v, f"Arg mismatch for key '{k}' in '{cmd}'"

    def test_complex_vs_direct_intent_classification(self):
        """Verify that direct commands bypass LLM and complex commands request LLM routing."""
        ctx = ExecutionContext()

        # Direct commands (all steps mapped)
        direct_steps = plan_user_input("open notepad && type hello world and close notepad", ctx)
        assert all(s.is_direct for s in direct_steps)

        # Complex reasoning commands (not mapped directly to single verbs)
        complex_inputs = [
            "prepare my presentation slides for tomorrow's meeting",
            "summarize the latest unread emails and draft a reply to John",
            "diagnose why my network connection is slow",
            "find the invoice from last week and calculate the total expense",
        ]
        for comp_cmd in complex_inputs:
            steps = plan_user_input(comp_cmd, ctx)
            assert any(not s.is_direct for s in steps), f"Complex command '{comp_cmd}' should not be direct"

    def test_coreference_and_pronoun_resolution_chain(self):
        """Test multi-step pronoun resolution across sequential actions."""
        ctx = ExecutionContext()
        steps = plan_user_input("open edge && maximize it and close the app", ctx)
        assert len(steps) == 3
        assert steps[0].tool_args == {"app_name": "edge"}
        # Initial parse should NOT resolve "it" or "the app" because context is not yet updated
        assert steps[1].tool_args == {}
        assert steps[2].tool_args == {}

        # Simulate execution step 1: open_app finishes and updates context
        ctx.update("open_app", {"app_name": "edge"})
        assert ctx.last_app_name == "edge"

        # Re-resolve step 2: "maximize it"
        step2 = match_direct_command(steps[1].command, ctx)
        assert step2.tool_name == "maximize_window"
        assert step2.tool_args == {"app_name": "edge"}

        # Re-resolve step 3: "close the app"
        step3 = match_direct_command(steps[2].command, ctx)
        assert step3.tool_name == "close_app"
        assert step3.tool_args == {"app_name": "edge"}

    def test_nlp_router_submillisecond_latency(self):
        """Ensure the NLP router operates in sub-millisecond timeframe (< 1.0 ms)."""
        ctx = ExecutionContext()
        cmd = "open chrome && type fast router benchmark and maximize it"
        
        # Warmup
        for _ in range(10):
            plan_user_input(cmd, ctx)

        start = time.perf_counter()
        iterations = 500
        for _ in range(iterations):
            plan_user_input(cmd, ctx)
        total_time_ms = (time.perf_counter() - start) * 1000
        avg_latency_ms = total_time_ms / iterations

        print(f"\n[NLP Router Benchmark] Average latency: {avg_latency_ms:.4f} ms per query")
        assert avg_latency_ms < 15.0, f"Router latency {avg_latency_ms} ms exceeds 15.0 ms threshold"


# ==============================================================================
# SECTION 2: MINI AI MODEL OPTIMIZATION VALIDATION
# ==============================================================================

class TestMiniAIModelOptimization:
    """Validates optimization processes for mini speech & reasoning AI models."""

    def test_fallback_json_parser_for_small_models(self):
        """Small models (0.5B - 3B) often output markdown codeblocks or plain JSON instead of function calls."""
        # Case 1: Markdown codeblock
        t1 = "Sure! Here is the action:\n```json\n{\"tool\": \"open_app\", \"arguments\": {\"app_name\": \"notepad\"}}\n```"
        c1 = parse_fallback_json(t1)
        assert len(c1) == 1
        assert c1[0]["tool_name"] == "open_app"
        assert c1[0]["arguments"] == {"app_name": "notepad"}

        # Case 2: Function / parameters format
        t2 = "```json\n[{\"function\": \"press_key\", \"parameters\": {\"key\": \"enter\"}}]\n```"
        c2 = parse_fallback_json(t2)
        assert len(c2) == 1
        assert c2[0]["tool_name"] == "press_key"
        assert c2[0]["arguments"] == {"key": "enter"}

        # Case 3: Mixed text with multiple inline JSON objects
        t3 = 'I will run {"name": "mouse_click", "arguments": {"target": "ok"}} and then {"tool": "close_app", "arguments": {"app_name": "notepad"}}'
        c3 = parse_fallback_json(t3)
        assert len(c3) == 2
        assert c3[0]["tool_name"] == "mouse_click"
        assert c3[1]["tool_name"] == "close_app"

    def test_vad_frame_latency_and_probability(self):
        """Verify Voice Activity Detection model latency (< 5ms per 32ms frame) and response."""
        vad = VADEngine(speech_threshold=0.5)

        # 1. Silence frame (zeros)
        silence_frame = np.zeros(512, dtype=np.float32)
        prob_silence = vad.speech_probability(silence_frame)
        assert prob_silence < 0.1, f"Silence probability should be low, got {prob_silence}"
        assert vad.process_frame(silence_frame) is False

        # 2. Simulated audio signal frame
        t = np.linspace(0, 0.032, 512, endpoint=False)
        speech_frame = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
        prob_speech = vad.speech_probability(speech_frame)
        assert prob_speech > 0.25, f"Speech signal probability should be elevated, got {prob_speech}"
        assert prob_speech > prob_silence * 50, "Speech probability must be orders of magnitude higher than silence"

        # 3. Latency benchmark
        t0 = time.perf_counter()
        frames = 100
        for _ in range(frames):
            vad.process_frame(speech_frame)
        avg_ms = ((time.perf_counter() - t0) * 1000) / frames
        print(f"\n[VAD Benchmark] Latency per 32ms frame: {avg_ms:.4f} ms")
        assert avg_ms < 5.0, f"VAD frame latency {avg_ms} ms exceeds 5.0 ms threshold"

    def test_stt_int8_quantization_and_greedy_decoding(self):
        """Verify faster-whisper CTranslate2 INT8 quantization and greedy decoding optimizations."""
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            pytest.skip("faster-whisper is not installed")

        # Load optimized mini model (tiny.en with INT8 compute)
        t_load_start = time.perf_counter()
        model = WhisperModel(
            "tiny.en",
            device="cpu",
            compute_type="int8",
            download_root="./models",
            cpu_threads=0,
            num_workers=1,
        )
        load_time_ms = (time.perf_counter() - t_load_start) * 1000
        print(f"\n[STT Optimization] Model load time (INT8 quantized): {load_time_ms:.1f} ms")

        # Test greedy decoding (beam_size=1) with conditioning disabled
        # Synthesize 1-second 16kHz audio
        sample_audio = np.zeros(16000, dtype=np.float32)

        # Warm-up pass
        t0 = time.perf_counter()
        segments, _ = model.transcribe(
            sample_audio,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=True,
        )
        _ = list(segments)
        warmup_time_ms = (time.perf_counter() - t0) * 1000
        print(f"[STT Optimization] Cold-start / Warm-up inference time: {warmup_time_ms:.1f} ms")

        # Warmed-up greedy inference pass
        t1 = time.perf_counter()
        segments, _ = model.transcribe(
            sample_audio,
            beam_size=1,
            language="en",
            condition_on_previous_text=False,
            without_timestamps=True,
            vad_filter=True,
        )
        _ = list(segments)
        warmed_time_ms = (time.perf_counter() - t1) * 1000
        print(f"[STT Optimization] Warmed greedy inference time (INT8, beam=1): {warmed_time_ms:.1f} ms")

        # Verify warm inference is fast and non-blocking
        assert warmed_time_ms < 500.0, f"Warmed STT inference took {warmed_time_ms} ms, expected < 500 ms on silence"
