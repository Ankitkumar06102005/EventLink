from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Virtue(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class Profile(models.Model):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('college', 'College'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    full_name = models.CharField(max_length=100, blank=True)
    class_name = models.CharField(max_length=50, blank=True)
    section = models.CharField(max_length=10, blank=True)
    net_number = models.CharField(max_length=20, blank=True)
    about_you = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    virtues = models.ManyToManyField(Virtue, blank=True)

    def __str__(self):
        return self.full_name or self.user.username


class Team(models.Model):
    name = models.CharField(max_length=100)
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='led_teams')
    members = models.ManyToManyField(User, related_name='teams', blank=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_events', null=True, blank=True)

    def __str__(self):
        return self.title

    @property
    def approved_teams_count(self):
        return self.registrations.filter(status='approved').count()

    @property
    def pending_count(self):
        return self.registrations.filter(status='pending').count()


class EventRegistration(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='registrations')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('team', 'event')  # prevent duplicate applications

    def __str__(self):
        return f"{self.team.name} → {self.event.title} [{self.status}]"


class Stage(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='stages')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.event.title} — Stage {self.order}: {self.name}"


class TeamProgress(models.Model):
    STATUS_CHOICES = (
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('eliminated', 'Eliminated'),
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='progress')
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='progress')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='not_started')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('team', 'stage')

    def __str__(self):
        return f"{self.team.name} @ {self.stage.name} [{self.status}]"


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
