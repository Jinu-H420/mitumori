<?php
/**
 * 曲げ見積り実績の一元管理API
 * GET: 実績一覧（JSON配列）を返す
 * POST: 実績一覧（JSON配列）を保存する
 */
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
  exit(0);
}

$dataDir = __DIR__ . '/../data';
$file = $dataDir . '/records.json';

if ($_SERVER['REQUEST_METHOD'] === 'GET') {
  if (!is_file($file)) {
    echo '[]';
    exit;
  }
  $raw = file_get_contents($file);
  $data = json_decode($raw, true);
  echo json_encode(is_array($data) ? $data : []);
  exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
  $body = file_get_contents('php://input');
  $data = json_decode($body, true);
  if (!is_array($data)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON array']);
    exit;
  }
  if (!is_dir($dataDir)) {
    mkdir($dataDir, 0755, true);
  }
  $ok = file_put_contents($file, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
  if ($ok === false) {
    http_response_code(500);
    echo json_encode(['error' => 'Failed to write file']);
    exit;
  }
  echo json_encode(['ok' => true]);
  exit;
}

http_response_code(405);
echo json_encode(['error' => 'Method not allowed']);
