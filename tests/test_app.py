import base64
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

spec = importlib.util.spec_from_file_location('campus_app', Path(__file__).resolve().parents[1] / 'VThacks_HokieCrew/app.py')
campus = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {'ELEVENLABS_API_KEY': '', 'GEMINI_API_KEY': '', 'TIGERDATA_URL': ''}):
    spec.loader.exec_module(campus)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = campus.app.test_client()

    def test_invalid_json_shapes(self):
        for body in [None, [], 'hello', {'query': []}, {'query': ' '}, {'type': 'bad'}]:
            response = self.client.post('/api/query', json=body)
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.get_json())

    def test_transcription_failure_never_routes(self):
        with patch.object(campus, 'transcribe_audio', side_effect=RuntimeError('Try again')), patch.object(campus, 'route_query') as route:
            response = self.client.post('/api/query', json={'type': 'voice', 'audio': 'abc'})
            self.assertEqual(response.status_code, 502)
            route.assert_not_called()

    def test_real_transcription_response_contract(self):
        from elevenlabs.types import SpeechToTextChunkResponseModel
        result = SpeechToTextChunkResponseModel(language_code='eng', language_probability=1, text='vegan food', words=[])
        fake = MagicMock()
        fake.speech_to_text.convert.return_value = result
        with patch.object(campus, 'elevenlabs_client', fake):
            self.assertEqual(campus.transcribe_audio(base64.b64encode(b'audio').decode()), 'vegan food')
            fake.speech_to_text.convert.assert_called_once()

    def test_invalid_audio_and_missing_transcript(self):
        fake = MagicMock()
        fake.speech_to_text.convert.return_value = SimpleNamespace()
        with patch.object(campus, 'elevenlabs_client', fake):
            for audio in ['%%%', base64.b64encode(b'audio').decode()]:
                with self.assertRaises(RuntimeError):
                    campus.transcribe_audio(audio)

    def test_voice_and_text_use_same_data_path(self):
        menus = pd.DataFrame([{'name': 'Tofu', 'is_vegan': True}, {'name': 'Beef', 'is_vegan': False}])
        restaurants = pd.DataFrame([{'name': 'Cafe', 'vegan': True}])
        def load(name):
            return menus if name.endswith('food_menus') else restaurants
        with patch.object(campus, 'load_table', side_effect=load), patch.object(campus, 'transcribe_audio', return_value='vegan food'), patch.object(campus, 'text_to_speech', return_value='sound'):
            for payload in [{'query': 'vegan food'}, {'type': 'voice', 'audio': 'abc'}]:
                response = self.client.post('/api/query', json={**payload, 'want_audio': True})
                self.assertEqual(response.status_code, 200)
                result = response.get_json()
                self.assertIn('Tofu', result['response'])
                self.assertNotIn('Beef', result['response'])
                self.assertEqual(result['audio'], 'sound')

    def test_missing_diet_flag_is_not_a_match(self):
        frame = pd.DataFrame([{'name': 'Unknown'}])
        self.assertTrue(campus.filter_dietary(frame, ['halal']).empty)
        self.assertTrue(campus.filter_dietary(frame, ['gluten-free'], menu=True).empty)

    def test_database_errors_return_json(self):
        with patch.object(campus, 'load_table', side_effect=RuntimeError('warehouse unavailable')):
            response = self.client.post('/api/query', json={'query': 'vegan food'})
            self.assertEqual(response.status_code, 503)
            self.assertIn('error', response.get_json())

    def test_warehouse_required(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(RuntimeError, 'DATABRICKS_WAREHOUSE_ID'):
            campus.load_table('workspace.default.food_menus')

    def test_sql_rows_convert_and_connections_close(self):
        connect = MagicMock()
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.description = [('name',), ('is_vegan',)]
        cursor.fetchall.return_value = [('Tofu', True)]
        config = SimpleNamespace(host='https://example.databricks.com', authenticate=lambda: {})
        with patch.dict(os.environ, {'DATABRICKS_WAREHOUSE_ID': 'abc', 'DATABRICKS_HTTP_PATH': ''}), patch.object(campus, 'Config', return_value=config), patch.object(campus.sql, 'connect', connect):
            frame = campus.load_table('workspace.default.food_menus')
        self.assertEqual(frame.iloc[0]['name'], 'Tofu')
        cursor.execute.assert_called_once_with('SELECT * FROM `workspace`.`default`.`food_menus`')
        self.assertEqual(connect.call_args.kwargs['http_path'], '/sql/1.0/warehouses/abc')
        self.assertEqual(connect.call_args.kwargs['server_hostname'], 'example.databricks.com')
        connect.return_value.__exit__.assert_called_once()

    def test_table_identifier_is_validated(self):
        with self.assertRaises(ValueError):
            campus.load_table('workspace.default.food; DROP TABLE x')

    def test_nullable_bus_telemetry(self):
        routes = pd.DataFrame([{'route_code': 'A', 'route_name': 'Walmart', 'stops': None}])
        buses = pd.DataFrame([{'route_code': 'A', 'vehicle_id': '1', 'eta_next_stop_min': None}])
        with patch.object(campus, 'load_table', side_effect=[routes, buses]):
            result = campus.recommend_bus_route('bus to Walmart')
        self.assertIn('ETA: unavailable', result)
        for value in [None, float('nan'), 'bad', float('inf')]:
            self.assertIsNone(campus.optional_number(value, integer=True))

    def test_events_use_notebook_table_names(self):
        with patch.object(campus, 'load_table', return_value=pd.DataFrame()) as load:
            campus.find_events_and_clubs('club')
        self.assertEqual([c.args[0] for c in load.call_args_list], ['workspace.default.ii_campus_events', 'workspace.default.ii_student_clubs', 'workspace.default.ii_cultural_centers'])

    def test_gemini_does_not_rewrite_dietary_matches(self):
        with patch.object(campus, 'gemini_model', True), patch.object(campus, 'gemini_generate', return_value='food') as generate, patch.object(campus, 'recommend_food', return_value='Verified flags only'):
            self.assertEqual(campus.route_query('vegan food'), 'Verified flags only')
            generate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
