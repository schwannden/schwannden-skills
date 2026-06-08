# Serializer Patterns

Comprehensive guide to DRF serializer usage, validation, and common patterns.

> **DRF Docs:** https://www.django-rest-framework.org/api-guide/serializers/
> **Validators:** https://www.django-rest-framework.org/api-guide/validators/

---

## Contents

1. Serializer Types: When to Use What
2. Field-Level Validation
3. Object-Level Validation
4. Validators (Declarative)
5. Custom Error Messages on Built-in Fields
6. Nested Serializers
7. Accessing Request Context
8. Advanced Defaults
9. Partial Updates
10. SerializerMethodField
11. Validation Execution Order

## 1. Serializer Types: When to Use What

| Type | Use When |
|------|----------|
| `Serializer` | No model backing, or you need full control over fields |
| `ModelSerializer` | Standard CRUD on a Django model (most common) |
| `HyperlinkedModelSerializer` | API uses hyperlinks instead of PKs for relations |
| `ListSerializer` | Custom bulk create/update logic (auto-used with `many=True`) |

### ModelSerializer (Default Choice)

```python
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'name', 'email', 'created']
        read_only_fields = ['id', 'created']
```

**Rules:**
- Always list fields explicitly — never use `fields = '__all__'` (security risk, leaks new fields)
- Use `read_only_fields` for computed/auto fields
- Use `extra_kwargs` to customize field behavior without redeclaring

### Plain Serializer (For Non-Model Data)

```python
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
```

---

## 2. Field-Level Validation

Use `validate_<field_name>` for single-field custom validation:

```python
class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists.",
                code="email_exists"  # Always provide code for i18n
            )
        return value  # Always return the (possibly transformed) value
```

**Note:** `validate_<field>` is NOT called if the field has `required=False` and the field is omitted from input.

---

## 3. Object-Level Validation

Use `validate()` for cross-field validation:

```python
class DateRangeSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()

    def validate(self, data):
        if data['start'] >= data['end']:
            raise serializers.ValidationError(
                "End must be after start.",
                code="invalid_date_range"
            )
        return data
```

---

## 4. Validators (Declarative)

### On Fields

```python
from rest_framework.validators import UniqueValidator

class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            message="This email is already registered."
        )]
    )
```

### On the Serializer (Meta.validators)

```python
from rest_framework.validators import UniqueTogetherValidator

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['room', 'date', 'user']
        validators = [
            UniqueTogetherValidator(
                queryset=Booking.objects.all(),
                fields=['room', 'date'],
                message="This room is already booked for that date."
            )
        ]
```

### Available Validators

| Validator | Purpose |
|-----------|---------|
| `UniqueValidator` | Field-level uniqueness |
| `UniqueTogetherValidator` | Multi-field uniqueness (replaces model `unique_together`) |
| `UniqueForDateValidator` | Unique per date |
| `UniqueForMonthValidator` | Unique per month |
| `UniqueForYearValidator` | Unique per year |

### Custom Reusable Validator (Function or Class)

```python
# Function
def validate_positive(value):
    if value <= 0:
        raise serializers.ValidationError(
            "Must be positive.",
            code="not_positive"
        )

# Class (parameterized)
class MultipleOf:
    def __init__(self, base):
        self.base = base

    def __call__(self, value):
        if value % self.base != 0:
            raise serializers.ValidationError(
                f"Must be a multiple of {self.base}.",
                code="not_multiple"
            )

# Usage
score = serializers.IntegerField(validators=[MultipleOf(10)])
```

---

## 5. Custom Error Messages on Built-in Fields

```python
class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = ['email', 'age']
        extra_kwargs = {
            'email': {
                'error_messages': {
                    'required': 'Email is required.',
                    'invalid': 'Enter a valid email address.',
                    'blank': 'Email cannot be blank.',
                }
            },
            'age': {
                'error_messages': {
                    'required': 'Age is required.',
                    'invalid': 'Enter a valid number.',
                    'min_value': 'Must be at least {min_value}.',
                    'max_value': 'Must be at most {max_value}.',
                }
            },
        }
```

Common error codes per field type:
- **All fields:** `required`, `null`
- **CharField:** `blank`, `max_length`, `min_length`
- **IntegerField/FloatField:** `invalid`, `max_value`, `min_value`
- **EmailField:** `invalid`
- **ChoiceField:** `invalid_choice`
- **RelatedField:** `does_not_exist`, `incorrect_type`

---

## 6. Nested Serializers

### Read-Only Nesting (Simple)

```python
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['bio', 'avatar_url']

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'profile']
```

### Writable Nesting (Must Override create/update)

```python
class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ['id', 'email', 'profile']

    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        user = User.objects.create(**validated_data)
        Profile.objects.create(user=user, **profile_data)
        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        instance.email = validated_data.get('email', instance.email)
        instance.save()

        if profile_data:
            profile = instance.profile
            profile.bio = profile_data.get('bio', profile.bio)
            profile.save()

        return instance
```

Nested validation errors are returned nested:
```json
{
  "profile": {
    "bio": [{"message": "This field may not be blank.", "code": "blank"}]
  }
}
```

---

## 7. Accessing Request Context

```python
class MySerializer(serializers.ModelSerializer):
    class Meta:
        model = MyModel
        fields = ['name', 'owner']

    def validate_name(self, value):
        request = self.context.get('request')
        if request and MyModel.objects.filter(
            owner=request.user, name=value
        ).exists():
            raise serializers.ValidationError(
                "You already have an item with this name.",
                code="duplicate_name"
            )
        return value
```

**Note:** Generic views pass `request` in context automatically. With `APIView`, pass it explicitly:
```python
serializer = MySerializer(data=request.data, context={'request': request})
```

---

## 8. Advanced Defaults

```python
from rest_framework.serializers import CurrentUserDefault, CreateOnlyDefault

class ItemSerializer(serializers.ModelSerializer):
    owner = serializers.HiddenField(default=CurrentUserDefault())
    created_at = serializers.DateTimeField(
        default=CreateOnlyDefault(timezone.now),
        read_only=True
    )
```

---

## 9. Partial Updates

```python
serializer = MySerializer(instance, data=request.data, partial=True)
serializer.is_valid(raise_exception=True)
serializer.save()
```

With `partial=True`, fields not present in the input are skipped (not set to None).

---

## 10. SerializerMethodField

Read-only computed fields:

```python
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
```

---

## 11. Validation Execution Order

DRF runs validation in this order:
1. **Field-level deserialization** (`to_internal_value`) — type checking, required, blank, null
2. **Field-level validators** — `validators=[...]` on the field
3. **`validate_<field>`** methods — custom per-field validation
4. **Serializer-level validators** — `Meta.validators` (UniqueTogetherValidator, etc.)
5. **`validate()`** method — cross-field validation

If any step fails, subsequent steps for that field are skipped, but other fields continue validation (so you get all errors at once).
