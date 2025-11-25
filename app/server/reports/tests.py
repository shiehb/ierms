from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone
from datetime import date, timedelta

from .models import AccomplishmentReport, ReportMetric, ReportAttachment, ReportComment

User = get_user_model()


class AccomplishmentReportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_report(self):
        report = AccomplishmentReport.objects.create(
            title='Test Report',
            report_type='monthly',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            summary='Test summary',
            key_achievements='Test achievements',
            created_by=self.user
        )
        
        self.assertEqual(report.title, 'Test Report')
        self.assertEqual(report.status, 'draft')
        self.assertEqual(report.created_by, self.user)
        self.assertIsNotNone(report.created_at)


class AccomplishmentReportAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            is_staff=True
        )
        
        self.report_data = {
            'title': 'Test Report',
            'report_type': 'monthly',
            'period_start': (date.today() - timedelta(days=30)).isoformat(),
            'period_end': date.today().isoformat(),
            'summary': 'Test summary',
            'key_achievements': 'Test achievements',
            'challenges_faced': 'Test challenges',
            'recommendations': 'Test recommendations'
        }
    
    def test_create_report_authenticated(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/reports/', self.report_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AccomplishmentReport.objects.count(), 1)
    
    def test_create_report_unauthenticated(self):
        response = self.client.post('/api/reports/', self.report_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_list_reports(self):
        # Create a report
        report = AccomplishmentReport.objects.create(
            title='Test Report',
            report_type='monthly',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            summary='Test summary',
            key_achievements='Test achievements',
            created_by=self.user
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/reports/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_submit_report(self):
        report = AccomplishmentReport.objects.create(
            title='Test Report',
            report_type='monthly',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            summary='Test summary',
            key_achievements='Test achievements',
            created_by=self.user
        )
        
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f'/api/reports/{report.id}/submit/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        report.refresh_from_db()
        self.assertEqual(report.status, 'submitted')
        self.assertIsNotNone(report.submission_date)
    
    def test_review_report(self):
        report = AccomplishmentReport.objects.create(
            title='Test Report',
            report_type='monthly',
            period_start=date.today() - timedelta(days=30),
            period_end=date.today(),
            summary='Test summary',
            key_achievements='Test achievements',
            created_by=self.user,
            status='submitted'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f'/api/reports/{report.id}/review/', {'action': 'approve'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')
        self.assertEqual(report.reviewed_by, self.admin_user)
        self.assertIsNotNone(report.reviewed_at)
