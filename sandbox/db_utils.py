def get_or_create(session, cls, commit=False, **kwargs):
    if hasattr(cls, "_unique_columns"):
        unique_columns = cls._unique_columns
        cropped_kwargs = {k: v for k, v in kwargs.items() if k in unique_columns}
        instance = session.query(cls).filter_by(**cropped_kwargs).first()
        if instance:
            return instance
        else:
            instance = cls(**kwargs)
            session.add(instance)
            if commit:
                session.commit()
            return instance
    else:
        instance = cls(**kwargs)
        session.add(instance)
        if commit:
            session.commit()
        return instance
