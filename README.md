<div align="center">

# INTEGRATED_ESTABLISHMENTS_REGULATORY_MANAGEMENT_SYSTEM

*Empowering Compliance Through Seamless Regulation Management*

![last-commit](https://img.shields.io/github/last-commit/shiehb/integrated_establishments_regulatory_management_system)
![repo-top-language](https://img.shields.io/github/languages/top/shiehb/integrated_establishments_regulatory_management_system)
![repo-language-count](https://img.shields.io/github/languages/count/shiehb/integrated_establishments_regulatory_management_system)

*Built with the tools and technologies:*

![JSON](https://img.shields.io/badge/JSON-000000?style=flat&logo=json&logoColor=white)
![Markdown](https://img.shields.io/badge/Markdown-000000?style=flat&logo=markdown&logoColor=white)
![npm](https://img.shields.io/badge/npm-CB3837?style=flat&logo=npm&logoColor=white)
![Autoprefixer](https://img.shields.io/badge/Autoprefixer-DD3735?style=flat&logo=autoprefixer&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-FF4438?style=flat&logo=redis&logoColor=white)
![PostCSS](https://img.shields.io/badge/PostCSS-DD3A0A?style=flat&logo=postcss&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=flat&logo=leaflet&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat&logo=celery&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Zod](https://img.shields.io/badge/Zod-3E67B1?style=flat&logo=zod&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)
![ESLint](https://img.shields.io/badge/ESLint-4B32C3?style=flat&logo=eslint&logoColor=white)
![Axios](https://img.shields.io/badge/Axios-5A29E4?style=flat&logo=axios&logoColor=white)
![React Hook Form](https://img.shields.io/badge/React%20Hook%20Form-EC5990?style=flat&logo=reacthookform&logoColor=white)
![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat&logo=chartdotjs&logoColor=white)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Testing](#testing)
- [Project Structure](#project-structure)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Integrated Establishments Regulatory Management System is a comprehensive platform combining modern frontend tooling with robust backend architecture to streamline environmental regulation workflows. Built with React, Tailwind CSS, and Django, it supports scalable, secure, and efficient management of inspections, establishments, and compliance data.

### Core Features

- 🧩 **Fast Development:** Optimized React setup with Vite and Hot Module Replacement for rapid iteration
- 🎨 **Consistent UI:** Custom Tailwind styling, animations, and a modular component library
- 🔒 **Secure & Role-Based:** Advanced access controls, user management, and security features
- 🗺️ **Rich Mapping Tools:** Interactive maps with geospatial editing, markers, and overlays
- 📊 **Extensive Backend:** APIs for inspections, reports, notifications, and audit logs integrated with Django models
- 🛠️ **Developer-Friendly:** Comprehensive testing, utility functions, and a scalable architecture supporting complex workflows

---

## Getting Started

### Prerequisites

This project requires the following dependencies:

- **Programming Languages:** JavaScript (ES6+), Python 3.8+
- **Package Managers:** npm (Node.js 16+), pip (Python 3.8+)
- **Database:** MySQL/MariaDB
- **Cache/Message Broker:** Redis
- **Task Queue:** Celery (with Redis as broker)

### Installation

Build integrated_establishments_regulatory_management_system from the source and install dependencies:

1. **Clone the repository:**
   ```sh
   git clone https://github.com/shiehb/ierms
   ```

2. **Navigate to the project directory:**
   ```sh
   cd integrated_establishments_regulatory_management_system
   ```

3. **Install frontend dependencies:**
   ```sh
   npm install
   ```

4. **Install backend dependencies:**
   ```sh
   # Create a virtual environment (recommended)
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   
   # Install Python packages
   pip install -r server/requirements.txt
   ```

5. **Set up environment variables:**
   - Copy `.env.example` to `.env` (if available) or create a `.env` file in the `server` directory
   - Configure database, Redis, and other service credentials

6. **Set up the database:**
   ```sh
   cd server
   python manage.py migrate
   python manage.py createsuperuser
   ```

### Usage

**Frontend Development Server:**
```sh
npm run dev
```
The frontend will be available at `http://localhost:5173` (or the port specified by Vite).

**Backend Development Server:**
```sh
cd server
python manage.py runserver
```
The backend API will be available at `http://localhost:8000`.

**Build for Production:**
```sh
# Build frontend
npm run build

# The built files will be in the dist/ directory
```

**Run Celery Worker (for background tasks):**
```sh
cd server
celery -A core worker -l info
```

**Run Celery Beat (for scheduled tasks):**
```sh
cd server
celery -A core beat -l info
```

### Testing

**Frontend Testing:**
```sh
npm test
```

**Backend Testing:**
```sh
cd server
pytest
# or
python manage.py test
```

---

## Project Structure

```
integrated_establishments_regulatory_management_system/
├── src/                    # Frontend React application
│   ├── components/         # Reusable React components
│   ├── pages/              # Page components
│   ├── services/           # API service functions
│   ├── utils/              # Utility functions
│   ├── contexts/           # React contexts
│   ├── hooks/              # Custom React hooks
│   ├── constants/          # Application constants
│   └── config/             # Configuration files
├── server/                 # Django backend application
│   ├── core/               # Core Django settings and configuration
│   ├── establishments/     # Establishments app
│   ├── inspections/        # Inspections app
│   ├── reports/            # Reports app
│   ├── laws/               # Laws app
│   ├── users/              # User management app
│   ├── notifications/      # Notifications app
│   ├── audit/              # Audit logging app
│   └── system_config/      # System configuration app
├── public/                 # Static public assets
├── dist/                   # Production build output
└── venv/                   # Python virtual environment (gitignored)
```

---

## Features

### Frontend Features
- **Modern React Architecture:** Built with React 19, React Router, and React Hook Form
- **Interactive Maps:** Leaflet integration for geospatial visualization and editing
- **Data Visualization:** Chart.js and Recharts for analytics and reporting
- **Form Management:** Zod validation with React Hook Form
- **Responsive Design:** Tailwind CSS for mobile-first responsive layouts
- **Drag & Drop:** @hello-pangea/dnd for intuitive UI interactions

### Backend Features
- **RESTful API:** Django REST Framework for comprehensive API endpoints
- **Authentication:** JWT-based authentication with role-based access control
- **Background Tasks:** Celery integration for asynchronous task processing
- **File Management:** Support for document uploads, signatures, and media files
- **Audit Logging:** Comprehensive audit trail for system activities
- **Excel Export:** OpenPyXL for generating Excel reports
- **PDF Generation:** PDF generation for reports and legal documents

---

## Technology Stack

### Frontend
- **React 19** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **React Router** - Client-side routing
- **Axios** - HTTP client
- **Leaflet** - Interactive maps
- **Chart.js / Recharts** - Data visualization
- **Zod** - Schema validation
- **React Hook Form** - Form management

### Backend
- **Django 4.2** - Web framework
- **Django REST Framework** - API framework
- **Celery** - Distributed task queue
- **Redis** - Caching and message broker
- **MySQL** - Database
- **Pillow** - Image processing
- **OpenPyXL** - Excel file handling

---

## Deployment

For deployment instructions, see:
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
- [RAILWAY_QUICK_START.md](./RAILWAY_QUICK_START.md)
- [RAILWAY_STEP_BY_STEP.md](./RAILWAY_STEP_BY_STEP.md)

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<div align="left">

[⬆ Return to top](#integrated_establishments_regulatory_management_system)

</div>
