from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Q
from establishments.models import Establishment
from inspections.models import Inspection
from establishments.serializers import EstablishmentSerializer
from inspections.serializers import InspectionSerializer
from users.serializers import UserSerializer
from Levenshtein import distance as levenshtein_distance

User = get_user_model()

def fuzzy_match(query, text, threshold=2):
    """
    Returns True if query fuzzy matches text within threshold edits.
    threshold: max character differences allowed (insertions/deletions/substitutions)
    Examples:
      - "sainff" matches "saint" (distance=2)
      - "restrant" matches "restaurant" (distance=2)
    """
    if not query or not text:
        return False
        
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Exact substring match
    if query_lower in text_lower:
        return True
    
    # Check each word in text for fuzzy match
    for word in text_lower.split():
        if levenshtein_distance(query_lower, word) <= threshold:
            return True
        
        # Also check if query is close to beginning of word
        if len(word) >= len(query_lower):
            word_prefix = word[:len(query_lower)]
            if levenshtein_distance(query_lower, word_prefix) <= threshold:
                return True
    
    return False

class GlobalSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            q = request.query_params.get("q", "").strip()
            
            # If no search query, return empty results
            if not q:
                return Response({
                    "establishments": [],
                    "users": [],
                    "inspections": [],
                    "suggestions": []
                })

            # Establishments query
            try:
                est_qs = Establishment.objects.all()
                if q:
                    est_qs = est_qs.filter(
                        Q(name__icontains=q)
                        | Q(nature_of_business__icontains=q)
                        | Q(province__icontains=q)
                        | Q(city__icontains=q)
                        | Q(barangay__icontains=q)
                    )
                establishments = EstablishmentSerializer(est_qs[:10], many=True).data
            except Exception as e:
                print(f"Establishment search error: {e}")
                establishments = []

            # Users query
            try:
                user_qs = User.objects.all()
                if q:
                    user_qs = user_qs.filter(
                        Q(first_name__icontains=q)
                        | Q(last_name__icontains=q)
                        | Q(email__icontains=q)
                        | Q(userlevel__icontains=q)
                    )
                users = UserSerializer(user_qs[:10], many=True).data
            except Exception as e:
                print(f"User search error: {e}")
                users = []

            # Inspections query - Handle ManyToMany relationship
            try:
                insp_qs = Inspection.objects.prefetch_related("establishments").all()
                if q:
                    insp_qs = insp_qs.filter(
                        Q(code__icontains=q) |
                        Q(law__icontains=q) |
                        Q(establishments__name__icontains=q)
                    ).distinct()
                inspections = InspectionSerializer(insp_qs[:10], many=True).data
            except Exception as e:
                print(f"Inspection search error: {e}")
                inspections = []

            # Generate search suggestions
            suggestions = self.generate_search_suggestions(q, establishments, users, inspections)

            return Response({
                "establishments": establishments,
                "users": users,
                "inspections": inspections,
                "suggestions": suggestions
            })
        
        except Exception as e:
            print(f"Global search error: {e}")
            import traceback
            traceback.print_exc()
            return Response({
                "establishments": [],
                "users": [],
                "inspections": [],
                "suggestions": [],
                "error": str(e)
            }, status=500)

    def generate_search_suggestions(self, query, establishments, users, inspections):
        suggestions = []
        
        # Add establishment suggestions
        for est in establishments[:3]:
            suggestions.append({
                "type": "establishment",
                "name": est.get('name', ''),
                "description": f"Establishment in {est.get('city', '')}",
                "category": "Business",
                "icon": "🏢",
                "id": est.get('id')
            })
        
        # Add user suggestions
        for user in users[:3]:
            suggestions.append({
                "type": "user",
                "name": f"{user.get('first_name', '')} {user.get('last_name', '')}",
                "description": f"User - {user.get('userlevel', '')}",
                "category": "People",
                "icon": "👤",
                "id": user.get('id')
            })
        
        # Add inspection suggestions
        for insp in inspections[:3]:
            # Handle ManyToMany establishments field
            establishments_data = insp.get('establishments', [])
            if isinstance(establishments_data, list) and len(establishments_data) > 0:
                establishment_name = establishments_data[0].get('name', 'Unknown') if isinstance(establishments_data[0], dict) else str(establishments_data[0])
            elif isinstance(establishments_data, dict):
                establishment_name = establishments_data.get('name', 'Unknown')
            else:
                establishment_name = 'Unknown'
                
            suggestions.append({
                "type": "inspection",
                "name": f"Inspection {insp.get('code', '')}",
                "description": f"Inspection for {establishment_name}",
                "category": "Inspections",
                "icon": "📋",
                "id": insp.get('id')
            })
        
        # Add generic suggestions based on search query
        if len(suggestions) < 5:
            generic_suggestions = [
                {"type": "suggestion", "name": f"Search '{query}' in establishments", "category": "Search", "icon": "🔍"},
                {"type": "suggestion", "name": f"Search '{query}' in users", "category": "Search", "icon": "🔍"},
                {"type": "suggestion", "name": f"Search '{query}' in inspections", "category": "Search", "icon": "🔍"},
            ]
            suggestions.extend(generic_suggestions[:5 - len(suggestions)])
        
        return suggestions[:8]  # Limit total suggestions


class SearchSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            # Handle both q and q[q] params (axios sometimes nests objects)
            q = request.query_params.get("q", "")
            if not q:
                # Try to get from nested param
                q_dict = request.query_params.get("q[q]", "")
                if q_dict:
                    q = q_dict
            q = q.strip()
            
            role = request.query_params.get("role", "public")
            if not role:
                role = request.query_params.get("role[role]", "public")
            
            if not q or len(q) < 2:
                return Response({"suggestions": []})

            # Get current user's profile for role-based filtering
            current_user = request.user
            user_section = getattr(current_user, 'section', None)
            
            suggestions = []

            # ============ USER SUGGESTIONS ============
            # Role-based user search filtering - Only Admin can search users
            if role == 'Admin':
                # Admin: See all users except admin accounts
                all_users = User.objects.exclude(is_active=False).exclude(is_superuser=True).exclude(userlevel='Admin')
            else:
                # All other roles: No user search access
                all_users = User.objects.none()

            # Fuzzy match users
            matching_users = []
            for user in all_users:
                full_name = f"{user.first_name} {user.last_name}"
                if (fuzzy_match(q, user.first_name or '', threshold=2) or
                    fuzzy_match(q, user.last_name or '', threshold=2) or
                    fuzzy_match(q, full_name, threshold=2) or
                    fuzzy_match(q, user.email or '', threshold=2)):
                    matching_users.append(user)
                    
                    if len(matching_users) >= 5:
                        break
            
            for user in matching_users:
                suggestions.append({
                    "type": "user",
                    "id": user.id,
                    "name": f"{user.first_name} {user.last_name}",
                    "description": f"{user.email} • {user.userlevel}",
                    "category": "Users",
                    "updated_at": user.updated_at.isoformat() if hasattr(user, 'updated_at') else None,
                    "path": "/users"
                })

            # ============ ESTABLISHMENT SUGGESTIONS ============
            # All roles can see all establishments (public information)
            all_establishments = Establishment.objects.all()

            # Fuzzy match establishments
            matching_establishments = []
            for est in all_establishments:
                if (fuzzy_match(q, est.name, threshold=2) or 
                    fuzzy_match(q, est.nature_of_business or '', threshold=2) or
                    fuzzy_match(q, est.city or '', threshold=2)):
                    matching_establishments.append(est)
                    
                    if len(matching_establishments) >= 5:
                        break

            for est in matching_establishments:
                suggestions.append({
                    "type": "establishment",
                    "id": est.id,
                    "name": est.name,
                    "description": f"{est.city}",
                    "category": "Establishments",
                    "updated_at": est.updated_at.isoformat() if hasattr(est, 'updated_at') else None,
                    "path": "/establishments"
                })

            # ============ INSPECTION SUGGESTIONS ============
            # Role-based inspection filtering
            if role in ['Admin', 'Division Chief']:
                # Admin/Division Chief: See all inspections
                all_inspections = Inspection.objects.prefetch_related('establishments').all()
            elif role == 'Section Chief':
                # Section Chief: See inspections in their section
                if user_section:
                    # Split section by comma and strip whitespace from each law
                    section_laws = [law.strip() for law in user_section.split(',')]
                    all_inspections = Inspection.objects.prefetch_related('establishments').filter(
                        law__in=section_laws
                    )
                else:
                    all_inspections = Inspection.objects.none()
            elif role == 'Unit Head':
                # Unit Head: See inspections in their unit
                if user_section:
                    all_inspections = Inspection.objects.prefetch_related('establishments').filter(
                        law=user_section
                    )
                else:
                    all_inspections = Inspection.objects.none()
            elif role == 'Monitoring Personnel':
                # Monitoring Personnel: See assigned inspections
                all_inspections = Inspection.objects.prefetch_related('establishments').filter(
                    assigned_to=current_user
                )
            elif role == 'Legal Unit':
                # Legal Unit: See inspections in legal review
                all_inspections = Inspection.objects.prefetch_related('establishments').filter(
                    current_status__in=['LEGAL_REVIEW', 'NOV_SENT', 'NOO_SENT']
                )
            else:
                # Public, Inspector: No inspection search access
                all_inspections = Inspection.objects.none()

            # Fuzzy match inspections
            matching_inspections = []
            for insp in all_inspections:
                establishment_names = [e.name for e in insp.establishments.all()]
                
                code_match = fuzzy_match(q, insp.code or '', threshold=2)
                law_match = fuzzy_match(q, insp.law or '', threshold=2)
                est_match = any(fuzzy_match(q, name, threshold=2) for name in establishment_names)
                
                if code_match or law_match or est_match:
                    matching_inspections.append(insp)
                    
                    if len(matching_inspections) >= 5:
                        break

            for insp in matching_inspections:
                establishment_names = [e.name for e in insp.establishments.all()[:1]]
                establishment_name = establishment_names[0] if establishment_names else 'Unknown'
                status = insp.current_status if hasattr(insp, 'current_status') else 'CREATED'
                
                suggestions.append({
                    "type": "inspection",
                    "id": insp.id,
                    "name": f"Inspection {insp.code}",
                    "description": f"{establishment_name} • {status}",
                    "category": "Inspections",
                    "updated_at": insp.updated_at.isoformat() if hasattr(insp, 'updated_at') else None,
                    "path": "/inspections"
                })

            # Add navigation with role-based permissions
            navigation_items = [
                {'name': 'Dashboard', 'path': '/', 'type': 'navigation', 'roles': ['all']},
                {'name': 'Map', 'path': '/map', 'type': 'navigation', 'roles': ['all']},
                {'name': 'Establishments', 'path': '/establishments', 'type': 'navigation', 'roles': ['all']},
                {'name': 'Inspections', 'path': '/inspections', 'type': 'navigation', 'roles': ['all']},
                {'name': 'Users', 'path': '/users', 'type': 'navigation', 'roles': ['Admin']},
                {'name': 'Billing Records', 'path': '/billing', 'type': 'navigation', 'roles': ['Legal Unit']},
                {'name': 'System Configuration', 'path': '/system-config', 'type': 'navigation', 'roles': ['Admin']},
                {'name': 'Backup & Restore', 'path': '/database-backup', 'type': 'navigation', 'roles': ['Admin']},
                {'name': 'Help Center', 'path': '/help', 'type': 'navigation', 'roles': ['all']},
                {'name': 'Notifications', 'path': '/notifications', 'type': 'navigation', 'roles': ['all']},
            ]

            # Filter navigation with fuzzy matching and role-based permissions
            matching_nav = [
                {
                    **item, 
                    'id': None,
                    'category': 'Navigation', 
                    'description': f'Go to {item["name"]} page',
                    'updated_at': None
                }
                for item in navigation_items 
                if fuzzy_match(q, item['name'], threshold=2)
                and ('all' in item['roles'] or role in item['roles'])
            ]
            
            suggestions.extend(matching_nav[:3])

            # Sort by relevance (exact matches first, then partial matches)
            def get_relevance_score(suggestion):
                name_lower = suggestion['name'].lower()
                query_lower = q.lower()
                
                # Exact match
                if name_lower == query_lower:
                    return 0
                # Starts with query
                elif name_lower.startswith(query_lower):
                    return 1
                # Contains query at word boundary
                elif f" {query_lower}" in f" {name_lower}":
                    return 2
                # Contains query anywhere
                elif query_lower in name_lower:
                    return 3
                # Partial match in description
                else:
                    return 4
            
            suggestions.sort(key=get_relevance_score)

            return Response({"suggestions": suggestions[:15]})
        
        except Exception as e:
            print(f"Search suggestions error: {e}")
            import traceback
            traceback.print_exc()
            return Response({"suggestions": [], "error": str(e)}, status=500)


class SearchFilterOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Distinct municipalities (cities) from establishments
        cities = (
            Establishment.objects.order_by("city")
            .values_list("city", flat=True)
            .distinct()
        )
        # Sectors: use inspections laws and establishment nature_of_business samples
        sections = (
            Inspection.objects.order_by("law")
            .values_list("law", flat=True)
            .distinct()
        )
        nature_samples = (
            Establishment.objects.order_by("nature_of_business")
            .values_list("nature_of_business", flat=True)
            .distinct()
        )

        # Combine into a unique sorted list for UI convenience
        sector_options = sorted({s for s in sections if s} | {n for n in nature_samples if n})

        return Response({
            "municipalities": [c for c in cities if c],
            "sectors": sector_options,
            "risk_levels": [],
        })