"""Production boundaries exercise the actual exporter, not a surrogate engine."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from app.services.ltspice_exporter import generate_asc_with_routing
from app.services.production import Execution, PipelineError, PipelineLimits, checkpoint, circuit_size, execution_context

FIXTURE = Path(__file__).resolve().parents[1] / 'circuits/rc_low_pass_filter.json'


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.circuit = json.loads(FIXTURE.read_text())

    def rejected(self, circuit, code, **kwargs):
        text, diagnostics, _ = generate_asc_with_routing(circuit, **kwargs)
        self.assertEqual('', text)
        self.assertIn(code, [d.code for d in diagnostics])
        self.assertTrue(all(d.stage for d in diagnostics))
        return diagnostics

    def test_size_classes(self):
        self.assertEqual(['small', 'small', 'medium', 'medium', 'large', 'large', 'extreme'],
                         [circuit_size(n) for n in (1, 20, 21, 100, 101, 500, 501)])

    def test_invalid_boundary_never_places(self):
        cases = [(None, 'INVALID_CIRCUIT'), ({}, 'INVALID_COMPONENTS'),
                 ({'components': [], 'wires': []}, 'INVALID_COMPONENTS')]
        for value in (None, [], True, float('nan')):
            circuit = copy.deepcopy(self.circuit)
            circuit['components'][0]['value'] = value
            if value is not None:
                cases.append((circuit, 'INVALID_NUMBER' if isinstance(value, float) else 'INVALID_VALUE'))
        for source, code in cases:
            with self.subTest(code=code), patch('app.services.ltspice_exporter.place_components') as place:
                self.rejected(source, code)
                place.assert_not_called()

    def test_unsupported_unwired_never_substituted(self):
        self.circuit['components'] = [{'reference': 'U1', 'type': 'LM358'}]
        self.circuit['wires'] = []
        diagnostics = self.rejected(self.circuit, 'UNSUPPORTED_COMPONENT')
        self.assertEqual('U1', diagnostics[0].component)

    def test_input_attack_cases(self):
        for field, value, code in [('value', '1k\nWIRE 0 0 16 0', 'INVALID_ATTRIBUTE'),
                                   ('value', 'not-a-resistance', 'INVALID_VALUE'),
                                   ('reference', '../R1', 'INVALID_COMPONENT_IDENTITY'),
                                   ('x', float('inf'), 'INVALID_NUMBER'),
                                   ('position', {'x': 'bad', 'y': 0}, 'INVALID_COORDINATE')]:
            with self.subTest(field=field, value=value):
                circuit = copy.deepcopy(self.circuit)
                circuit['components'][0][field] = value
                self.rejected(circuit, code)
        self.circuit['metadata'] = self.circuit
        self.rejected(self.circuit, 'CYCLIC_INPUT')

    def test_electrical_errors_stop_before_routing(self):
        for endpoint, code in [('R1.missing', 'UNRESOLVED_PIN'), ('R9.1', 'MISSING_COMPONENT'), ('', 'EMPTY_ENDPOINT')]:
            circuit = copy.deepcopy(self.circuit)
            circuit['wires'][0]['to'] = endpoint
            with self.subTest(endpoint=endpoint), patch('app.services.ltspice_exporter.route_nets') as route:
                self.rejected(circuit, code)
                route.assert_not_called()

    def test_limits_cover_input_pins_nets_and_export(self):
        for limits in (PipelineLimits(max_components=1), PipelineLimits(max_pins=1),
                       PipelineLimits(max_nets=1), PipelineLimits(max_export_bytes=1),
                       PipelineLimits(max_routing_segments=1), PipelineLimits(max_wires=1)):
            with self.subTest(limits=limits):
                self.rejected(self.circuit, 'RESOURCE_LIMIT', limits=limits)

    def test_timeout_is_transactional(self):
        self.rejected(self.circuit, 'PIPELINE_TIMEOUT', limits=PipelineLimits(total_seconds=0.000001))

    def test_request_context_resets_after_failure(self):
        execution = Execution(PipelineLimits(max_routing_iterations=1))
        execution.stage = 'routing'
        with self.assertRaises(PipelineError), execution_context(execution):
            checkpoint(iterations=2)
        checkpoint(iterations=999999999)

    def test_metrics_and_determinism(self):
        original = copy.deepcopy(self.circuit)
        results = []
        for _ in range(3):
            metrics = {}
            text, diagnostics, routed = generate_asc_with_routing(self.circuit, metrics=metrics)
            self.assertTrue(text, diagnostics)
            self.assertEqual(2, metrics['componentCount'])
            for stage in ('input_validation', 'net_building', 'validation', 'layout', 'pin_resolution', 'routing', 'optimization', 'export', 'post_export_validation'):
                self.assertIn(stage, metrics['stagesMs'])
            results.append((text, routed.net_geometries, routed.flags))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(original, self.circuit)

    def test_serialization_corruption_blocks_export(self):
        with patch('app.services.ltspice_exporter._wire_line', return_value='WIRE 0 0 16 0'):
            text, diagnostics, _ = generate_asc_with_routing(self.circuit)
        self.assertEqual('', text)
        self.assertIn('SERIALIZED_WIRE_MISMATCH', [d.code for d in diagnostics])

    def test_atomic_save_preserves_original_on_replace_failure(self):
        import tempfile
        from circuits.repository import CircuitRepository
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'circuit.json'
            path.write_text(json.dumps(self.circuit))
            original = path.read_bytes()
            with patch('circuits.repository.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    CircuitRepository(Path(directory)).update_circuit(self.circuit['id'], self.circuit)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual([path], list(Path(directory).iterdir()))

    def test_config_is_finite_and_positive(self):
        for value in (0, -1, float('nan'), float('inf'), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PipelineLimits(total_seconds=value)
        with patch.dict('os.environ', {'SPICECRAFT_MAX_COMPONENTS': '42'}):
            self.assertEqual(42, PipelineLimits.from_environment().max_components)


class ProductionBoundaryTests(unittest.TestCase):
    setUp = ProductionTests.setUp
    rejected = ProductionTests.rejected

    def test_unicode_and_direct_input_byte_limits(self):
        for field in ('name', 'description'):
            circuit = copy.deepcopy(self.circuit)
            circuit[field] = '\ud800'
            self.rejected(circuit, 'INVALID_STRING')
        self.rejected(self.circuit, 'RESOURCE_LIMIT', limits=PipelineLimits(max_input_bytes=20))

    def test_stage_iteration_limits_block_export(self):
        for limits in (PipelineLimits(max_layout_iterations=1),
                       PipelineLimits(max_routing_iterations=1),
                       PipelineLimits(max_optimization_iterations=1)):
            with self.subTest(limits=limits):
                self.rejected(self.circuit, 'RESOURCE_LIMIT', limits=limits)

    def test_repeated_stages_share_time_budget(self):
        execution = Execution(PipelineLimits(layout_seconds=1), started=0,
                              stage='layout', stage_started=0)
        with patch('app.services.production.perf_counter', return_value=0.6):
            execution.transition('validation')
            execution.transition('layout')
        with patch('app.services.production.perf_counter', return_value=1.1):
            with self.assertRaises(PipelineError):
                execution.check()

    def test_connectivity_checks_active_budget(self):
        from app.services.connectivity import build_connectivity
        execution = Execution(PipelineLimits(), started=0, stage_started=0)
        with execution_context(execution), self.assertRaises(PipelineError):
            build_connectivity(self.circuit)

    def test_invalid_routing_option_types_are_diagnostics(self):
        from app.services.connectivity import build_connectivity
        from app.services.ltspice_exporter import place_components
        from app.services.routing import RoutingOptions, route_nets
        model = build_connectivity(self.circuit)
        layouts = place_components(self.circuit['components'], model)
        for options in (RoutingOptions(max_order_attempts=1.5), RoutingOptions(clearance=None),
                        RoutingOptions(max_search_states=float('inf')), RoutingOptions(envelope_margins=(True,)),
                        RoutingOptions(allow_crossings='yes')):
            with self.subTest(options=options):
                result = route_nets(model, layouts, options=options)
                self.assertEqual([], result.net_geometries)
                self.assertIn('INVALID_ROUTING_OPTIONS', [d.code for d in result.diagnostics])

    def test_unwired_serialized_pin_corruption_blocks_export(self):
        from app.services.regression_validation import parse_asc_semantics
        circuit = copy.deepcopy(self.circuit)
        circuit['wires'] = []
        def corrupt(text):
            parsed = parse_asc_semantics(text)
            parsed['components'][0]['pins'].pop('1')
            return parsed
        with patch('app.services.export_safety.parse_asc_semantics', side_effect=corrupt):
            self.rejected(circuit, 'SERIALIZED_PIN_SET_MISMATCH')

    def test_export_exception_is_transactional(self):
        from app.services.asc_validation import AscExportError, ExportDiagnostic, ERROR
        with patch('app.services.ltspice_exporter.place_components', side_effect=AscExportError([
                ExportDiagnostic(ERROR, 'TEST_LAYOUT_ERROR', 'Layout validation failed')])):
            diagnostics = self.rejected(self.circuit, 'TEST_LAYOUT_ERROR')
        self.assertEqual('layout', diagnostics[0].stage)

    def test_concurrent_request_budgets_are_isolated(self):
        from concurrent.futures import ThreadPoolExecutor
        def export(limit):
            metrics = {}
            text, diagnostics, _ = generate_asc_with_routing(self.circuit, limits=limit, metrics=metrics)
            return bool(text), [d.code for d in diagnostics], metrics
        with ThreadPoolExecutor(max_workers=2) as pool:
            good, bad = list(pool.map(export, [PipelineLimits(), PipelineLimits(max_components=1)]))
        self.assertTrue(good[0])
        self.assertFalse(bad[0])
        self.assertIn('RESOURCE_LIMIT', bad[1])
        self.assertEqual(0, good[2]['errorCount'])


class CircuitAPITests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.exceptions import RequestValidationError
        from fastapi.testclient import TestClient
        from app.request_limits import CircuitRequestLimits, circuit_http_error, circuit_validation_error
        from starlette.exceptions import HTTPException as StarletteHTTPException
        from app.routers import circuits
        self.circuit = json.loads(FIXTURE.read_text())
        self.routes = circuits
        self.app = FastAPI()
        self.app.add_middleware(CircuitRequestLimits)
        self.app.add_exception_handler(RequestValidationError, circuit_validation_error)
        self.app.add_exception_handler(StarletteHTTPException, circuit_http_error)
        self.app.include_router(circuits.router)
        self.client = TestClient(self.app)
        self.url = '/circuits/' + self.circuit['id']

    def test_valid_save_reaches_repository(self):
        self.circuit['metadata'] = {'author': 'Preserved author', 'revision': 3}
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=self.circuit), \
                patch.object(self.routes.repository, 'update_circuit', return_value=self.circuit) as update:
            response = self.client.put(self.url, json=self.circuit)
        self.assertEqual(200, response.status_code, response.text)
        update.assert_called_once()
        self.assertEqual(self.circuit['metadata'], update.call_args.args[1]['metadata'])
        self.assertEqual(self.circuit['metadata'], response.json()['metadata'])

    def test_request_validation_is_structured_without_input_echo(self):
        for body in (b'{broken', b'{}', b'{"components":NaN}'):
            with self.subTest(body=body):
                response = self.client.put(self.url, content=body, headers={'Content-Type': 'application/json'})
                self.assertEqual(422, response.status_code, response.text)
                detail = response.json()['detail']
                self.assertEqual('input_validation', detail['stage'])
                self.assertFalse(detail['retryable'])
                self.assertTrue(detail['diagnostics'])
                self.assertTrue(all('input' not in d for d in detail['diagnostics']))

    def test_decoder_integer_limit_error_is_structured(self):
        response = self.client.put(self.url, content='{"value":' + '9' * 5000 + '}',
                                   headers={'Content-Type': 'application/json'})
        self.assertEqual(400, response.status_code)
        self.assertEqual('input_validation', response.json()['detail']['stage'])
        self.assertFalse(response.json()['detail']['retryable'])

    def test_deep_json_is_rejected_before_decoding(self):
        response = self.client.put(self.url, content='[' * 1100 + '0' + ']' * 1100,
                                   headers={'Content-Type': 'application/json'})
        self.assertEqual(413, response.status_code)
        self.assertEqual('RESOURCE_LIMIT', response.json()['detail']['code'])

    def test_string_brackets_do_not_count_as_nesting(self):
        circuit = copy.deepcopy(self.circuit)
        circuit['description'] = '["\\' * 200
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=circuit), \
                patch.object(self.routes.repository, 'update_circuit', return_value=circuit):
            response = self.client.put(self.url, json=circuit)
        self.assertEqual(200, response.status_code, response.text)

    def test_save_budget_failure_never_writes(self):
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=self.circuit), \
                patch.object(self.routes.repository, 'update_circuit') as update, \
                patch('app.routers.circuits.PipelineLimits.from_environment', return_value=PipelineLimits(max_nets=1)):
            response = self.client.put(self.url, json=self.circuit)
        self.assertEqual(503, response.status_code, response.text)
        self.assertEqual('net_building', response.json()['detail']['stage'])
        update.assert_not_called()

    def test_failed_export_has_no_attachment_or_partial_asc(self):
        invalid = copy.deepcopy(self.circuit)
        invalid['wires'][0]['to'] = 'missing.1'
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=invalid):
            response = self.client.get(self.url + '/export/asc')
        self.assertEqual(422, response.status_code)
        self.assertNotIn('content-disposition', response.headers)
        self.assertEqual('validation', response.json()['detail']['stage'])

    def test_internal_error_does_not_leak_exception(self):
        with patch.object(self.routes.repository, 'get_circuit_by_id', side_effect=OSError('private disk path')):
            response = self.client.get(self.url)
        self.assertEqual(500, response.status_code)
        self.assertNotIn('private disk path', response.text)
        self.assertEqual('INTERNAL_ERROR', response.json()['detail']['code'])

    def test_missing_circuit_has_structured_error(self):
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=None):
            response = self.client.get(self.url)
        self.assertEqual(404, response.status_code)
        self.assertFalse(response.json()['detail']['retryable'])

    def test_list_and_detail_response_contract(self):
        self.circuit['metadata'] = {'author': 'Preserved author', 'revision': 3}
        with patch.object(self.routes.repository, 'get_all_circuits', return_value=[self.circuit]), \
                patch.object(self.routes.repository, 'get_circuit_by_id', return_value=self.circuit):
            listing = self.client.get('/circuits')
            detail = self.client.get(self.url)
        self.assertEqual(200, listing.status_code)
        self.assertEqual(200, detail.status_code)
        self.assertEqual([detail.json()], listing.json())
        self.assertEqual(self.circuit['metadata'], detail.json()['metadata'])

    def test_successful_export_has_valid_download_contract(self):
        circuit = copy.deepcopy(self.circuit)
        circuit['name'] = 'Unsafe / filename " ' + 'x' * 200
        with patch.object(self.routes.repository, 'get_circuit_by_id', return_value=circuit):
            response = self.client.get(self.url + '/export/asc')
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual('application/octet-stream', response.headers['content-type'])
        self.assertTrue(response.text.startswith('Version 4\nSHEET '))
        self.assertRegex(response.headers['content-disposition'], r'^attachment; filename="[A-Za-z0-9_-]{1,120}\.asc"$')

    def test_id_mismatch_never_writes(self):
        with patch.object(self.routes.repository, 'update_circuit') as update:
            response = self.client.put('/circuits/different', json=self.circuit)
        self.assertEqual(400, response.status_code)
        self.assertEqual('CIRCUIT_ID_MISMATCH', response.json()['detail']['code'])
        update.assert_not_called()

    def test_validation_diagnostics_include_safe_field_location(self):
        response = self.client.put(self.url, json={})
        self.assertEqual(422, response.status_code)
        diagnostics = response.json()['detail']['diagnostics']
        self.assertTrue(any(d['location'] == ['body', 'components'] for d in diagnostics))
        self.assertTrue(all('input' not in d for d in diagnostics))


class RequestBodyTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(self, messages, limits, headers=()):
        from app.request_limits import CircuitRequestLimits
        self.forwarded, self.sent = [], []
        async def app(scope, receive, send):
            self.forwarded.append(await receive())
        async def receive():
            return messages.pop(0)
        async def send(message):
            self.sent.append(message)
        await CircuitRequestLimits(app, limits)(
            {'type': 'http', 'path': '/circuits/test', 'method': 'PUT', 'headers': list(headers)}, receive, send)

    async def test_streamed_body_is_reassembled(self):
        await self.invoke([{'type': 'http.request', 'body': b'{', 'more_body': True},
                           {'type': 'http.request', 'body': b'}'}], PipelineLimits())
        self.assertEqual(b'{}', self.forwarded[0]['body'])

    async def test_stream_limit_without_content_length(self):
        await self.invoke([{'type': 'http.request', 'body': b'123', 'more_body': True},
                           {'type': 'http.request', 'body': b'456'}], PipelineLimits(max_input_bytes=5))
        self.assertFalse(self.forwarded)
        self.assertEqual(413, self.sent[0]['status'])

    async def test_disconnect_does_not_forward_partial_request(self):
        await self.invoke([{'type': 'http.disconnect'}], PipelineLimits())
        self.assertFalse(self.forwarded)
        self.assertFalse(self.sent)

    async def test_invalid_encoding_is_structured(self):
        await self.invoke([{'type': 'http.request', 'body': b'\xff'}], PipelineLimits())
        self.assertFalse(self.forwarded)
        self.assertEqual(422, self.sent[0]['status'])

    async def test_immediately_available_chunks_still_obey_timeout(self):
        from app.request_limits import CircuitRequestLimits
        messages = []
        async def app(scope, receive, send):
            self.fail('Timed-out body must not reach the app')
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': True}
        async def send(message):
            messages.append(message)
        await CircuitRequestLimits(app, PipelineLimits(request_body_seconds=0.001))(
            {'type': 'http', 'path': '/circuits/test', 'method': 'PUT'}, receive, send)
        self.assertEqual(408, messages[0]['status'])

    async def test_request_body_timeout(self):
        import asyncio
        from app.request_limits import CircuitRequestLimits
        messages = []
        async def app(scope, receive, send):
            self.fail('Timed-out body must not reach the app')
        async def receive():
            await asyncio.Event().wait()
        async def send(message):
            messages.append(message)
        await CircuitRequestLimits(app, PipelineLimits(request_body_seconds=0.001))(
            {'type': 'http', 'path': '/circuits/test', 'method': 'PUT'}, receive, send)
        self.assertEqual(408, messages[0]['status'])


if __name__ == '__main__':
    unittest.main()
