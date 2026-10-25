import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export default async function setup() {
  const root = fileURLToPath(new URL('../..', import.meta.url));
  const database = process.env.DECISIONIQ_DB_PATH;
  if (!database || resolve(database) === resolve(root, 'data/dashboard.sqlite3')) {
    throw new Error(
      'Browser checks require DECISIONIQ_DB_PATH pointing to the same separate test database used by the QA server.',
    );
  }
  process.env.FORESIGHT_TEST_ADMIN_EMAIL = `browser-admin-${randomBytes(6).toString('hex')}@example.test`;
  process.env.FORESIGHT_TEST_ADMIN_PASSWORD = randomBytes(24).toString('base64url');
  execFileSync(
    resolve(root, '.venv/bin/python'),
    [
      '-c',
      `
import json, sys
from decisioniq.dashboard import store
from decisioniq.dashboard.auth import password_hash
account = json.load(sys.stdin)
store.initialize()
with store.connect() as connection:
    connection.execute("INSERT INTO users VALUES (?,?,?,?,1,?)", (store.uid(), account['email'], 'Browser administrator', password_hash(account['password']), store.stamp()))
    connection.execute("DELETE FROM auth_limits")
`,
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        DECISIONIQ_DB_PATH: resolve(database),
        MPLCONFIGDIR: '/tmp/foresight-mpl',
      },
      input: JSON.stringify({
        email: process.env.FORESIGHT_TEST_ADMIN_EMAIL,
        password: process.env.FORESIGHT_TEST_ADMIN_PASSWORD,
      }),
      stdio: ['pipe', 'pipe', 'pipe'],
    },
  );
}
