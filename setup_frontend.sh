#!/bin/bash

PROJECT_NAME="pc-price-frontend"

echo "=========================================="
echo "Vue 3 + Tailwind CSS Setup for Rocky Linux"
echo "=========================================="

if ! command -v node &> /dev/null; then
    echo "Installing Node.js 20 LTS..."
    curl -fsSL https://rpm.nodesource.com∏/setup_20.x | bash -
    dnf install -y nodejs
    
    if ! command -v node &> /dev/null; then
        echo "Node.js installation failed. Check network or dnf."
        exit 1
    fi
else
    echo "Node.js installed: $(node -v)"
fi

if [ -d "$PROJECT_NAME" ]; then
    echo "Directory $PROJECT_NAME exists. Skipping creation."
else
    echo "Creating Vite project..."
    npm create vite@latest "$PROJECT_NAME" -- --template vue -y
fi

cd "$PROJECT_NAME" || exit

echo "Installing dependencies..."
npm install
npm install axios
npm install -D tailwindcss@3.4.17 postcss autoprefixer

echo "Configuring Tailwind..."

cat <<EOF > tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
EOF

cat <<EOF > postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
EOF

echo "Setting up global styles..."
cat <<EOF > src/style.css
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF

mkdir -p src/components

echo "Configuring firewall..."
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=8080/tcp
    firewall-cmd --permanent --add-port=5173/tcp
    firewall-cmd --reload
    echo "Firewall ports opened: $(firewall-cmd --list-ports)"
else
    echo "firewall-cmd not found. Skipping firewall setup."
fi

echo "=========================================="
echo "Setup Complete"
echo "=========================================="
echo "Next steps:"
echo "1. cd $PROJECT_NAME"
echo "2. Add App.vue and ProductDetail.vue to src/"
echo "3. npm run dev -- --host --port 8080"
echo "=========================================="