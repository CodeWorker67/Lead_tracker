import secrets
from pathlib import Path


def main():
	env_path = Path('.env')
	api_key = secrets.token_urlsafe(32)

	if env_path.exists():
		lines = env_path.read_text().splitlines()
		found = False

		for i, line in enumerate(lines):
			if line.startswith('API_KEY='):
				lines[i] = f'API_KEY={api_key}'
				found = True
				break

		if not found:
			lines.append(f'API_KEY={api_key}')

		env_path.write_text('\n'.join(lines) + '\n')
	else:
		env_path.write_text(f'API_KEY={api_key}')

	print('✅ API_KEY обновлен в .env')


if __name__ == '__main__':
	main()
